"""Shared helper for reference-data tables that carry a UNIQUE(name)."""


def revive_or_flag_duplicate(db, model, name: str, exclude_id: int):
    """Decide what to do when a name is submitted that is not live but once was.

    Reference-data tables (recipe categories, table zones) use soft delete, and
    MySQL cannot make a UNIQUE constraint partial. So after "Desserts" is soft
    deleted the row still owns that name, and a plain INSERT of a new "Desserts"
    fails with IntegrityError 1062. The user experiences this as "I deleted the
    category and now I cannot add it back".

    Rather than weakening the constraint (which would then permit two genuinely
    live rows with the same name), a soft-deleted row carrying the submitted
    name is revived and returned. Its id is preserved, so any existing foreign
    keys -- recipes pointing at a deleted category -- come back with it.

    Returns (row_to_revive_or_None, is_name_taken_by_a_live_row).

    Caller must still commit.
    """
    live = db.query(model).filter(
        model.name == name,
        model.is_deleted == False,
    ).first()

    if live is not None and live.id != exclude_id:
        return None, True

    tombstone = db.query(model).filter(
        model.name == name,
        model.is_deleted == True,
    ).order_by(model.id.asc()).first()

    return tombstone, False