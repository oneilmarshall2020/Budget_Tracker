from fastapi import APIRouter, HTTPException
from sqlmodel import select

from auth import CurrentUser
from categorize import SUGGESTED, keyword_matches, learnable, match_rule, suggest_keyword
from database import SessionDep
from helpers import category_fits, get_owned_or_404
from models import Category, CategoryKind, CategoryRule, RuleApply, RuleCreate, RuleUpdate, Transaction

router = APIRouter(tags=["Keyword rules"])


def check_category(session, category_id: int, user) -> Category:
    return get_owned_or_404(session, Category, category_id, user, "Category")


def user_rules(session, user) -> list[CategoryRule]:
    return session.exec(select(CategoryRule).where(CategoryRule.user_id == user.id)).all()


def find_rule(session, user, keyword: str) -> CategoryRule | None:
    return session.exec(
        select(CategoryRule).where(CategoryRule.user_id == user.id, CategoryRule.keyword == keyword)
    ).first()


def check_keyword_free(session, user, keyword: str, ignore_id: int | None = None) -> None:
    """A keyword can only point to one of your categories."""
    existing = find_rule(session, user, keyword)
    if existing and existing.id != ignore_id:
        owner = session.get(Category, existing.category_id)
        raise HTTPException(
            status_code=400,
            detail=f'"{keyword}" is already a keyword for {owner.name if owner else "another category"}. '
            "Remove it there first.",
        )


def matching_transactions(session, user, keyword: str, category: Category, exclude_id: int | None):
    """Your transactions this keyword covers that would change to `category`."""
    return [
        t for t in session.exec(select(Transaction).where(Transaction.user_id == user.id)).all()
        if t.id != exclude_id
        and t.category_id != category.id
        and category_fits(category, t.type)
        and keyword_matches(keyword, t.description)
    ]


# These three are declared before /rules/{rule_id} routes so their paths aren't read as ids.
@router.get("/rules/suggest")
def suggest_rule(
    session: SessionDep,
    user: CurrentUser,
    description: str,
    category_id: int,
    exclude_id: int | None = None,
):
    """You're changing a transaction's category: what could the app learn from that?

    keyword:           the keyword it would remember (an existing matching one, or a new one)
    rule_category_id:  that keyword's current category, if it already exists
    others:            how many other transactions it covers that would change too
    """
    category = check_category(session, category_id, user)
    if not learnable(description):
        return {"keyword": None, "rule_id": None, "rule_category_id": None, "others": 0}
    rule = match_rule(description, user_rules(session, user))
    keyword = rule.keyword if rule else suggest_keyword(description)
    if not keyword:
        return {"keyword": None, "rule_id": None, "rule_category_id": None, "others": 0}
    return {
        "keyword": keyword,
        "rule_id": rule.id if rule else None,
        "rule_category_id": rule.category_id if rule else None,
        "others": len(matching_transactions(session, user, keyword, category, exclude_id)),
    }


@router.post("/rules/remember")
def remember_rule(rule_in: RuleCreate, session: SessionDep, user: CurrentUser) -> CategoryRule:
    """Point this keyword at this category, creating it if it's new. Unlike POST /rules/,
    an existing keyword is moved instead of refused: you asked for it explicitly."""
    check_category(session, rule_in.category_id, user)
    rule = find_rule(session, user, rule_in.keyword)
    if rule:
        rule.category_id = rule_in.category_id
    else:
        rule = CategoryRule(**rule_in.model_dump(), user_id=user.id)
    session.add(rule)
    session.commit()
    session.refresh(rule)
    return rule


@router.post("/rules/apply")
def apply_rule(body: RuleApply, session: SessionDep, user: CurrentUser):
    """Re-categorize every other transaction the keyword covers."""
    category = check_category(session, body.category_id, user)
    changed = matching_transactions(session, user, body.keyword, category, body.exclude_id)
    for transaction in changed:
        transaction.category_id = category.id
        session.add(transaction)
    session.commit()
    return {"updated": len(changed)}


@router.get("/rules/")
def read_rules(session: SessionDep, user: CurrentUser) -> list[CategoryRule]:
    return session.exec(
        select(CategoryRule).where(CategoryRule.user_id == user.id).order_by(CategoryRule.keyword)
    ).all()


@router.post("/rules/")
def create_rule(rule_in: RuleCreate, session: SessionDep, user: CurrentUser) -> CategoryRule:
    check_category(session, rule_in.category_id, user)
    check_keyword_free(session, user, rule_in.keyword)
    rule = CategoryRule(**rule_in.model_dump(), user_id=user.id)
    session.add(rule)
    session.commit()
    session.refresh(rule)
    return rule


@router.patch("/rules/{rule_id}")
def update_rule(
    rule_id: int, rule_update: RuleUpdate, session: SessionDep, user: CurrentUser
) -> CategoryRule:
    rule = get_owned_or_404(session, CategoryRule, rule_id, user, "Keyword")
    data = rule_update.model_dump(exclude_unset=True, exclude_none=True)
    if "category_id" in data:
        check_category(session, data["category_id"], user)
    if "keyword" in data:
        check_keyword_free(session, user, data["keyword"], ignore_id=rule.id)
    rule.sqlmodel_update(data)
    session.add(rule)
    session.commit()
    session.refresh(rule)
    return rule


@router.delete("/rules/{rule_id}")
def delete_rule(rule_id: int, session: SessionDep, user: CurrentUser):
    rule = get_owned_or_404(session, CategoryRule, rule_id, user, "Keyword")
    session.delete(rule)
    session.commit()
    return {"ok": True}


@router.post("/rules/suggested")
def add_suggested(session: SessionDep, user: CurrentUser):
    """Add the suggested categories and their keywords. Safe to run twice: anything you
    already have (same name, same keyword) is left alone."""
    categories_added, keywords_added = add_suggested_set(session, user)
    session.commit()
    return {"categories_added": categories_added, "keywords_added": keywords_added}


def add_suggested_set(session, user) -> tuple[int, int]:
    """The work behind /rules/suggested (demo accounts start with it too).
    Returns (categories added, keywords added). The caller commits."""
    categories = {
        c.name.lower(): c
        for c in session.exec(select(Category).where(Category.user_id == user.id)).all()
    }
    taken = {rule.keyword for rule in user_rules(session, user)}
    categories_added = keywords_added = 0

    for name, kind, keywords in SUGGESTED:
        category = categories.get(name.lower())
        if category is None:
            category = Category(name=name, kind=CategoryKind(kind), user_id=user.id)
            session.add(category)
            session.flush()  # get its id for the rules below
            categories[name.lower()] = category
            categories_added += 1
        for keyword in keywords:
            if keyword not in taken:
                session.add(CategoryRule(keyword=keyword, category_id=category.id, user_id=user.id))
                taken.add(keyword)
                keywords_added += 1

    session.flush()
    return categories_added, keywords_added
