import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from product_category import infer_category  # noqa: E402


class InferCategoryTest(unittest.TestCase):
    def test_life_lines(self):
        self.assertEqual(infer_category("第一金人壽傳富100外幣變額年金保險", "life"), "投資型保險")
        self.assertEqual(infer_category("南山人壽iLike享富利率變動型年金保險", "life"), "年金保險")
        self.assertEqual(infer_category("友邦人壽5599還本終身保險", "life"), "還本養老")
        self.assertEqual(infer_category("宏泰人壽新住院醫療保險附約", "life"), "健康醫療")
        self.assertEqual(infer_category("新光人壽i-can傷害保險", "life"), "意外傷害")
        self.assertEqual(infer_category("遠雄人壽美滿多利利率變動型增額終身壽險", "life"), "壽險保障")
        self.assertEqual(infer_category("中國人壽鑫收益投資標的批註條款", "life"), "投資型保險")

    def test_property_lines(self):
        self.assertEqual(infer_category("國泰產物汽車車體損失保險丙式", "property"), "車險")
        self.assertEqual(infer_category("國泰產物電梯意外責任保險", "property"), "責任保險")
        self.assertEqual(infer_category("南山產物個人旅行保險海外突發疾病醫療附加保險", "property"), "健康醫療")
        self.assertEqual(infer_category("兆豐產物安裝工程綜合保險預約保險", "property"), "工程保險")
        self.assertEqual(infer_category("臺灣產物住宅火災保險", "property"), "火災及住宅")
        self.assertEqual(infer_category("明台產物員工誠實保證保險", "property"), "信用保證")
        self.assertEqual(infer_category("安達產物行動裝置保險", "property"), "產險其他")

    def test_unknown_company(self):
        self.assertEqual(infer_category("INSTITUTE CARGO CLAUSES (A)", ""), "海上及貨物")
        self.assertEqual(infer_category("安達保險特定大眾運輸工具團體傷害附加條款", ""), "意外傷害")
        self.assertEqual(infer_category("郵政安平二倍保障終身壽險", ""), "壽險保障")


if __name__ == "__main__":
    unittest.main()
