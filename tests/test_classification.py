from patrol_planning.demand.classification import classify_incident


def test_classification_and_response_assumptions() -> None:
    assert classify_incident("ROBBERY").category == "urgent"
    assert classify_incident("ROBBERY").response_limit_periods == 0
    assert classify_incident("VEHICLE - STOLEN").category == "property"
    assert classify_incident("THEFT OF IDENTITY").category == "theft"
    assert classify_incident("VANDALISM - FELONY").category == "public_disorder"
    assert classify_incident("OTHER MISCELLANEOUS CRIME").category == "other"
