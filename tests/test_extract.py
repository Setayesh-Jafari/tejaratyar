import unittest

from agent import extract as ex
from agent import webutil as web


class ExtractTests(unittest.TestCase):
    def test_gold_supplier_legal_name(self):
        page = {"title": "Arabica Green Coffee Beans from China Manufacturers - Yunnan Changshengda Coffee Co., Ltd.", "org_names": [], "text": "Yunnan Changshengda Coffee Co., Ltd. manufactures Arabica green coffee beans in Yunnan."}
        ent = ex.extract_company_entity(page["title"], page["text"], "https://csdcoffee.goldsupplier.com/154569-Arabica-Green-Coffee-Beans/", page)
        self.assertEqual(ent["name"], "Yunnan Changshengda Coffee Co., Ltd.")
        self.assertTrue(ent["legal_name"])
        self.assertGreaterEqual(ent["confidence"], 0.8)

    def test_tam_trinh_legal_name(self):
        text = "Tam Trinh Import Export Co., Ltd. is a coffee processing factory in Lam Dong, Vietnam, exporting Arabica green coffee beans."
        ent = ex.extract_company_entity("Green Arabica Beans - Tam Trinh Coffee", text, "https://export.tamtrinhcoffee.com/product-category/green-arabica-beans/", {"title": "Tam Trinh Coffee", "text": text, "org_names": ["Tam Trinh Import Export Co., Ltd."]})
        self.assertEqual(ent["legal_name"], "Tam Trinh Import Export Co., Ltd.")

    def test_category_and_buyer_pages_are_not_suppliers(self):
        self.assertEqual(ex.page_kind("https://www.alibaba.com/green-coffee-bean-export-suppliers.html", "Green coffee suppliers", "350 suppliers"), "marketplace_category")
        self.assertEqual(ex.page_kind("https://example.com/wanted-coffee", "Wanted: green coffee", "Buyer from Turkey"), "buyer_or_lead")

    def test_irrelevant_green_pages_fail_product_gate(self):
        blob = "Green River College offers STEM and business degrees in Washington."
        self.assertLess(ex.product_match_score(blob, "Green Arabica coffee beans"), 0.35)
        self.assertFalse(ex.looks_like_supplier("Green River College", blob, "https://greenriver.edu", "Green Arabica coffee beans"))

    def test_cross_company_website_is_rejected(self):
        self.assertFalse(ex.website_fits_company("https://arabica.com/en", "% Arabica coffee shops and stores", "Yunnan Changshengda Coffee Co., Ltd.", ["arabica", "coffee", "beans"]))

    def test_untrusted_sentence_is_not_company(self):
        for bad in ["Ltd. AIBot OnlineThis conversa", "Arabica coffee Vietnam supplier Premier Vietnamese coffee bean export", "237+ Shades of Green Color"]:
            self.assertFalse(ex.is_credible_company_name(bad), bad)

    def test_source_log_deduplicates(self):
        store = []
        item = {"title": "Example", "url": "https://example.com/page?utm_source=x", "snippet": "evidence", "query": "q"}
        a = web.log_source(store, item, "stage", claim="claim")
        b = web.log_source(store, {**item, "url": "https://www.example.com/page"}, "stage", claim="claim")
        self.assertEqual(a, b)
        self.assertEqual(len(store), 1)


if __name__ == "__main__":
    unittest.main()
