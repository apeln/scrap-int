from fareframe.core.registry import available_sites, build_scraper
import fareframe.scrapers  # noqa: F401


def test_example_site_is_registered() -> None:
    assert "example-site" in available_sites()
    assert build_scraper("example-site").site_name == "example-site"


def test_aircanada_is_registered() -> None:
    assert "aircanada" in available_sites()
    assert build_scraper("aircanada").site_name == "aircanada"


def test_westjet_is_registered() -> None:
    assert "westjet" in available_sites()
    assert build_scraper("westjet").site_name == "westjet"
