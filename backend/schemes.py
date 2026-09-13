# schemes.py
# Matches a user's profile (age, income, land ownership, category) against our
# schemes.json dataset and returns only the schemes they are actually eligible for.

import json  # to read the schemes.json file

with open("../data/schemes.json", "r") as f:
    schemes_data = json.load(f)


def find_eligible_schemes(age, annual_income, owns_land, category):
    """
    Returns a list of schemes the user qualifies for, based on age, income,
    land ownership, and reservation category (General/OBC/SC/ST/EWS) rules
    defined in schemes.json.
    """

    eligible = []

    for scheme in schemes_data:
        age_ok = scheme["min_age"] <= age <= scheme["max_age"]
        income_ok = annual_income <= scheme["max_annual_income"]
        land_ok = (not scheme["requires_land"]) or owns_land
        category_ok = category in scheme["categories"]  # e.g. category-specific scholarships

        if age_ok and income_ok and land_ok and category_ok:
            eligible.append({
                "name": scheme["name"],
                "description": scheme["description"],
                "steps": scheme["steps"]
            })

    return eligible
