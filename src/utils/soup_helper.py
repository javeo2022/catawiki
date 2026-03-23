import bs4
from typing import Optional


def get_element_attribute_or_text(
    soup_object: bs4.element.Tag,
    selector: str,
    index: int = 0,
    separator: str = "",
    attribute: Optional[str] = None,
    default: str = ""
) -> str:
    """
    指定されたセレクタで要素を取得し、属性値またはテキストを返す。
    Args:
        soup_object: BeautifulSoupのオブジェクト
        selector: CSSセレクタ文字列
        index: 取得する要素のインデックス
        separator: テキスト取得時の区切り文字
        attribute: 取得したい属性名 (Noneの場合はテキスト)
        default: 見つからなかった場合の戻り値
    """
    elements = soup_object.select(selector)
    if elements and len(elements) > index:
        if attribute:
            return elements[index].get(attribute, default)
        else:
            return elements[index].get_text(separator=separator, strip=True)
    else:
        return default
