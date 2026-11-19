from types import SimpleNamespace

from app.routes.search import _display_title


def test_baseline_search_shows_case_name_instead_of_court_header():
    case = SimpleNamespace(title="IN THE SUPREME COURT OF INDIA", slug="puttaswamy_case",
                           full_text="IN THE SUPREME COURT OF INDIA\n\nK.S. Puttaswamy v. Union of India\nJUDGMENT")
    assert _display_title(case) == "K.S. Puttaswamy v. Union of India"
