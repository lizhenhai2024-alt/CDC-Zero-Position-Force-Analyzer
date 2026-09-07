from __future__ import annotations

PRODUCT_NAME = "CDC Test Data Analyzer"
COMPANY_ZH = "富奥东机工减振器有限公司"
COMPANY_EN = "FAWER-TOKICO SHOCK ABSORBER CO., LTD."
AUTHOR_DEPARTMENT_ZH = "研发院技术中心"
AUTHOR_NAME_ZH = "李振海"
RELEASE_DATE = "2026/9/7"
RELEASE_EDITION_ZH = "第1版"
RELEASE_EDITION_EN = "Release 1"


def product_signature(language: str = "zh_CN") -> str:
    if language == "zh_CN":
        return (
            f"{PRODUCT_NAME}\n"
            f"{COMPANY_ZH} / {COMPANY_EN}\n"
            f"编制：{AUTHOR_DEPARTMENT_ZH}   {AUTHOR_NAME_ZH}\n"
            f"发布日期：{RELEASE_DATE}   {RELEASE_EDITION_ZH}"
        )
    return (
        f"{PRODUCT_NAME}\n"
        f"{COMPANY_EN}\n"
        f"Prepared by: {AUTHOR_DEPARTMENT_ZH} / {AUTHOR_NAME_ZH}\n"
        f"Release date: {RELEASE_DATE}   {RELEASE_EDITION_EN}"
    )
