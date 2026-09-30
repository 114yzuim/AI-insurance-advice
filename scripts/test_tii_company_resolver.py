import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "sources" / "tii"))

from company_resolver import resolve_company  # noqa: E402


class ResolveCompanyTest(unittest.TestCase):
    def assertCompany(self, name, company, method):
        match = resolve_company(name)
        self.assertEqual((match.company_name, match.method), (company, method), name)

    def test_chinese_prefix(self):
        self.assertCompany("富邦產物住宅火災保險", "富邦產物", "cjk_prefix")
        self.assertCompany("國泰人壽真全意住院醫療健康保險附約", "國泰人壽", "cjk_prefix")

    def test_aliases_and_typos_map_to_canonical(self):
        self.assertCompany("國泰產物汽車保險", "國泰世紀產物", "cjk_prefix")
        self.assertCompany("法商法國巴黎人壽威利100變額年金保險", "法國巴黎人壽", "cjk_prefix")
        self.assertCompany("兆兆豐產物營建機具綜合保險", "兆豐產物", "cjk_prefix")
        self.assertCompany("富邦產險傷害保險", "富邦產物", "cjk_prefix")
        self.assertCompany("郵政簡易人壽平安保險", "中華郵政", "cjk_prefix")

    def test_longest_alias_wins(self):
        self.assertCompany("統一安聯人壽終身壽險", "統一安聯人壽", "cjk_prefix")
        self.assertCompany("中國信託人壽終身壽險", "中國信託人壽", "cjk_prefix")

    def test_leading_product_code(self):
        self.assertCompany("SB002富邦產物80%共保附加條款", "富邦產物", "cjk_prefix")
        self.assertCompany("TP45 富邦產物營造綜合保險", "富邦產物", "cjk_prefix")

    def test_english_prefix(self):
        self.assertCompany("HOTAI MARINE CARGO INSURANCE Cargo ISPS Endorsement", "和泰產物", "english_prefix")
        self.assertCompany("Chartis Taiwan Insurance 50/50 Clause", "美亞產物", "english_prefix")
        self.assertCompany("Cathay Century Insurance Hull Insurance", "國泰世紀產物", "english_prefix")
        self.assertCompany("TOKIO MARINE NEWA Products Liability", "新安東京海上產物", "english_prefix")

    def test_life_science_is_not_life_company(self):
        self.assertCompany("Chubb Life Science Liability Insurance", "安達產物", "english_prefix")
        self.assertCompany("Chubb Life Group Term Rider", "安達人壽", "english_prefix")

    def test_contains_and_brand(self):
        self.assertCompany("Automatic Reinstatement Clause (和泰產物保險金額自動恢復附加條款)", "和泰產物", "cjk_contains")
        self.assertCompany("兆豐網路損失及電子資料除外不保附加條款", "兆豐產物", "brand_prefix")

    def test_dual_brand_by_line(self):
        self.assertCompany("富邦保險海上保險MARINE EXTENSION CLAUSES", "富邦產物", "brand_line")
        self.assertCompany("國泰多福年年利率變動型終身保險", "國泰人壽", "brand_line")
        self.assertCompany("蘇黎世貨物運送人責任險", "蘇黎世產物", "brand_line")

    def test_ambiguous_or_generic_stays_unknown(self):
        # 安達 has both a life and a property company -> don't guess.
        self.assertCompany("安達保險住院醫療日額保險", "", "unknown")
        self.assertCompany("安達保險航空飛行團體傷害保險", "", "unknown")
        self.assertCompany("INSTITUTE CARGO CLAUSES (C)", "", "unknown")
        self.assertCompany("", "", "unknown")


if __name__ == "__main__":
    unittest.main()
