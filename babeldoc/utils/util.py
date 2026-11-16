from babeldoc.app_devs import config 

class LangMapping():
    "语言代码-语言"
    MAP = {
        "zh": "中文",
        "en": "英语",
        "ja": "日语",
        "ko": "韩语",
        "de": "德语",
        "fr": "法语",
        "es": "西班牙语",
        "pt": "葡萄牙语",
        "ru": "俄语",
        "it": "意大利语",
        "nl": "荷兰语",
        "sv": "瑞典语",
        "da": "丹麦语",
        "no": "挪威语",
        "fi": "芬兰语",
        "pl": "波兰语",
        "cs": "捷克语",
        "hu": "匈牙利语",
        "tr": "土耳其语",
        "vi": "越南语",
        "th": "泰语",
        "ar": "阿拉伯语",
        "hi": "印地语",
        "he": "希伯来语",
    }
    MAP_ENG = {
        "zh": "Chinese(simply)",
        "en": "English",
        "ja": "Japanese",
        "ko": "Korean",
        "de": "German",
        "fr": "French",
        "es": "Spanish",
        "pt": "Portuguese",
        "ru": "Russian",
        "it": "Italian",
        "nl": "Dutch",
        "sv": "Swedish",
        "da": "Danish",
        "no": "Norwegian",
        "fi": "Finnish",
        "pl": "Polish",
        "cs": "Czech",
        "hu": "Hungarian",
        "tr": "Turkish",
        "vi": "Vietnamese",
        "th": "Thai",
        "ar": "Arabic",
        "hi": "Hindi",
        "he": "Hebrew",
    }
    default_lang = None

    @classmethod 
    def get_default_lang(cls):
        "zh"
        lang = cls.default_lang or "zh"
        return cls.get_english_name(lang)

    @classmethod
    def set_default_lang(cls, lang: str):
        cls.default_lang = lang
    
    @classmethod
    def get_english_name(cls, code: str):
        name = cls.MAP_ENG.get(code)
        if name is not None:
            return name
        # 找不到再调用默认语言，只在缺失时才执行
        return cls.MAP_ENG.get(cls.get_default_lang(), "zh")
