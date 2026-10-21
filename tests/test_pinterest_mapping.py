import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from pinterest_rss_publisher import (
    normalize_board_name,
    get_category_hashtags,
    build_pin_description,
    build_pinterest_payload,
    EXACT_CTA_STRING
)

def test_mappings():
    test_cases = [
        "new",
        "Hot deale India",
        "women's Fashion Deals",
        "Shoes &Sneaker Deals"
    ]
    
    expected_mappings = {
        "new": "Daily Shopping Deals India",
        "Hot deale India": "Hot Deals India",
        "women's Fashion Deals": "Women's Fashion Deals",
        "Shoes &Sneaker Deals": "Shoes & Sneaker Deals"
    }
    
    for raw in test_cases:
        norm = normalize_board_name(raw)
        assert norm == expected_mappings[raw], f"Failed for {raw}: got {norm}"
        tags = get_category_hashtags(norm)
        assert len(tags) >= 3, f"Expected at least 3 hashtags for {norm}"
        
        desc = build_pin_description("Save 70% on this item!", raw)
        assert EXACT_CTA_STRING in desc, f"CTA missing from description for {raw}"
        
        payload = build_pinterest_payload(
            title="Cool Product",
            raw_description="Big savings on product",
            destination_link="https://myntr.it/deal123",
            image_url="https://harshhaldankar.github.io/img.jpg",
            raw_board=raw
        )
        assert payload["board_id"] == expected_mappings[raw]
        assert EXACT_CTA_STRING in payload["description"]
        assert payload["link"] == "https://myntr.it/deal123"
        print(f"PASS: {raw!r} -> {norm!r}")
        print(f"      Hashtags: {tags}")
        print(f"      Description Preview:\n{desc}\n")

if __name__ == "__main__":
    test_mappings()
    print("ALL TESTS PASSED SUCCESSFULLY!")
