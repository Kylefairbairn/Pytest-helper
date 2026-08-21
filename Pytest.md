# conftest.py

def pytest_collection_finish(session):
    """Count requirements represented by the selected tests."""
    requirement_ids = set()
    requirement_tests = 0

    for item in session.items:
        marker = item.get_closest_marker("requirement")
        if marker is None:
            continue

        requirement_tests += 1

        # Example: @pytest.mark.requirement("REQ-123")
        if marker.args:
            requirement_ids.add(str(marker.args[0]))
        else:
            # If no requirement ID is supplied, count the test itself.
            requirement_ids.add(item.nodeid)

    session.config._requirement_count = len(requirement_ids)
    session.config._requirement_test_count = requirement_tests


def pytest_html_results_summary(prefix, summary, postfix, session):
    requirement_count = getattr(
        session.config,
        "_requirement_count",
        0,
    )
    requirement_test_count = getattr(
        session.config,
        "_requirement_test_count",
        0,
    )

    prefix.extend(
        [
            f"<p><strong>Requirements tested:</strong> "
            f"{requirement_count}</p>",
            f"<p><strong>Requirement test cases:</strong> "
            f"{requirement_test_count}</p>",
        ]
    )
