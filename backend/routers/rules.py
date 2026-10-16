from fastapi import APIRouter, HTTPException
from sqlmodel import select

from categorize import SUGGESTED, keyword_matches, learnable, match_rule, suggest_keyword
from database import SessionDep
from helpers import category_fits
from models import Category, CategoryKind, CategoryRule, RuleApply, RuleCreate, RuleUpdate, Transaction

router = APIRouter(tags=["Keyword rules"])


def check_category(session, category_id: int) -> Category:
    category = session.get(Category, category_id)
    if not category:
        raise HTTPException(status_code=404, detail="Category not found")
    return category


def check_keyword_free(session, keyword: str, ignore_id: int | None = None) -> None:
    """A keyword can only point to one category."""
    existing = session.exec(select(CategoryRule).where(CategoryRule.keyword == keyword)).first()
    if existing and existing.id != ignore_id:
        owner = session.get(Category, existing.category_id)
        raise HTTPException(
            status_code=400,
            detail=f'"{keyword}" is already a keyword for {owner.name if owner else "another category"}. '
            "Remove it there first.",
        )


def matching_transactions(session, keyword: str, category: Category, exclude_id: int | None):
    """Transactions this keyword covers that would change to `category`."""
    return [
        t for t in session.exec(select(Transaction)).all()
        if t.id != exclude_id
        and t.category_id != category.id
        and category_fits(category, t.type)
        and keyword_matches(keyword, t.description)
    ]


# These three are declared before /rules/{rule_id} routes so their paths aren't read as ids.
@router.get("/rules/suggest")
def suggest_rule(
    session: SessionDep, description: str, category_id: int, exclude_id: int | None = None
):
    """You're changing a transaction's category: what could the app learn from that?

    keyword:           the keyword it would remember (an existing matching one, or a new one)
    rule_category_id:  that keyword's current category, if it already exists
    others:            how many other transactions it covers that would change too
    """
    category = check_category(session, category_id)
    if not learnable(description):
        return {"keyword": None, "rule_id": None, "rule_category_id": None, "others": 0}
    rule = match_rule(description, session.exec(select(CategoryRule)).all())
    keyword = rule.keyword if rule else suggest_keyword(description)
    if not keyword:
        return {"keyword": None, "rule_id": None, "rule_category_id": None, "others": 0}
    return {
        "keyword": keyword,
        "rule_id": rule.id if rule else None,
        "rule_category_id": rule.category_id if rule else None,
        "others": len(matching_transactions(session, keyword, category, exclude_id)),
    }


@router.post("/rules/remember")
def remember_rule(rule_in: RuleCreate, session: SessionDep) -> CategoryRule:
    """Point this keyword at this category, creating it if it's new. Unlike POST /rules/,
    an existing keyword is moved instead of refused: you asked for it explicitly."""
    check_category(session, rule_in.category_id)
    rule = session.exec(select(CategoryRule).where(CategoryRule.keyword == rule_in.keyword)).first()
    if rule:
        rule.category_id = rule_in.category_id
    else:
        rule = CategoryRule(**rule_in.model_dump())
    session.add(rule)
    session.commit()
    session.refresh(rule)
    return rule


@router.post("/rules/apply")
def apply_rule(body: RuleApply, session: SessionDep):
    """Re-categorize every other transaction the keyword covers."""
    category = check_category(session, body.category_id)
    changed = matching_transactions(session, body.keyword, category, body.exclude_id)
    for transaction in changed:
        transaction.category_id = category.id
        session.add(transaction)
    session.commit()
    return {"updated": len(changed)}


@router.get("/rules/")
def read_rules(session: SessionDep) -> list[CategoryRule]:
    return session.exec(select(CategoryRule).order_by(CategoryRule.keyword)).all()


@router.post("/rules/")
def create_rule(rule_in: RuleCreate, session: SessionDep) -> CategoryRule:
    check_category(session, rule_in.category_id)
    check_keyword_free(session, rule_in.keyword)
    rule = CategoryRule(**rule_in.model_dump())
    session.add(rule)
    session.commit()
    session.refresh(rule)
    return rule


@router.patch("/rules/{rule_id}")
def update_rule(rule_id: int, rule_update: RuleUpdate, session: SessionDep) -> CategoryRule:
    rule = session.get(CategoryRule, rule_id)
    if not rule:
        raise HTTPException(status_code=404, detail="Keyword not found")
    data = rule_update.model_dump(exclude_unset=True, exclude_none=True)
    if "category_id" in data:
        check_category(session, data["category_id"])
    if "keyword" in data:
        check_keyword_free(session, data["keyword"], ignore_id=rule.id)
    rule.sqlmodel_update(data)
    session.add(rule)
    session.commit()
    session.refresh(rule)
    return rule


@router.delete("/rules/{rule_id}")
def delete_rule(rule_id: int, session: SessionDep):
    rule = session.get(CategoryRule, rule_id)
    if not rule:
        raise HTTPException(status_code=404, detail="Keyword not found")
    session.delete(rule)
    session.commit()
    return {"ok": True}


@router.post("/rules/suggested")
def add_suggested(session: SessionDep):
    """Add the suggested categories and their keywords. Safe to run twice: anything you
    already have (same name, same keyword) is left alone."""
    categories = {c.name.lower(): c for c in session.exec(select(Category)).all()}
    taken = set(session.exec(select(CategoryRule.keyword)).all())
    categories_added = keywords_added = 0

    for name, kind, keywords in SUGGESTED:
        category = categories.get(name.lower())
        if category is None:
            category = Category(name=name, kind=CategoryKind(kind))
            session.add(category)
            session.flush()  # get its id for the rules below
            categories[name.lower()] = category
            categories_added += 1
        for keyword in keywords:
            if keyword not in taken:
                session.add(CategoryRule(keyword=keyword, category_id=category.id))
                taken.add(keyword)
                keywords_added += 1

    session.commit()
    return {"categories_added": categories_added, "keywords_added": keywords_added}
