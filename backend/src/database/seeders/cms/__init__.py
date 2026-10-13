"""CMS seeders.

Bucket: cms -- cafe only

Import a specific seeder directly:

    from src.database.seeders.cms.recipe_category_seeder import seed_recipe_categories

`seeders/__init__.py` deliberately imports nothing. Seeder modules open
database sessions at call time, and eagerly importing them here would make
`import src.database.seeders` a side-effecting operation.
"""
