"""
敏感信息脱敏工具
用于日志、响应等场景下的敏感数据脱敏
"""
import re
from typing import Any, Dict, List, Union


class SensitiveDataMasker:
    """敏感信息脱敏器"""
    
    # 需要脱敏的字段名（不区分大小写）
    SENSITIVE_FIELDS = {
        "password", "pwd", "passwd", "secret", "token", "access_token",
        "refresh_token", "api_key", "apikey", "secret_key", "private_key",
        "credit_card", "card_number", "cvv", "ssn", "id_card", "phone",
        "mobile", "email", "address", "bank_account", "account_number"
    }
    
    # 脱敏规则
    MASK_RULES = {
        # 密码类：显示前2位，其余用 * 替代
        "password": lambda v: _mask_show_prefix(v, 2),
        "token": lambda v: _mask_show_prefix(v, 8),
        "api_key": lambda v: _mask_show_prefix(v, 4),
        "secret_key": lambda v: _mask_show_prefix(v, 4),
        
        # 银行卡号：显示前4位和后4位
        "credit_card": lambda v: _mask_card(v),
        "card_number": lambda v: _mask_card(v),
        "bank_account": lambda v: _mask_card(v),
        "account_number": lambda v: _mask_card(v),
        
        # 手机号：显示前3位和后4位
        "phone": lambda v: _mask_phone(v),
        "mobile": lambda v: _mask_phone(v),
        
        # 邮箱：显示前缀第一个字符
        "email": lambda v: _mask_email(v),
        
        # 身份证号：显示前3位和后4位
        "id_card": lambda v: _mask_id_card(v),
        "ssn": lambda v: _mask_id_card(v),
    }
    
    # 正则匹配模式
    _email_pattern = re.compile(r'[\w\.-]+@[\w\.-]+\.\w+')
    _phone_pattern = re.compile(r'1[3-9]\d{9}')
    _id_card_pattern = re.compile(r'\d{6}(19|20)\d{2}(0[1-9]|1[0-2])(0[1-9]|[12]\d|3[01])\d{3}[\dXx]')
    
    @classmethod
    def mask_dict(cls, data: Dict) -> Dict:
        """递归脱敏字典中的敏感字段"""
        if not isinstance(data, dict):
            return data
        
        result = {}
        for key, value in data.items():
            key_lower = key.lower()
            
            # 检查是否需要脱敏
            if key_lower in cls.SENSITIVE_FIELDS:
                mask_func = cls.MASK_RULES.get(key_lower, _default_mask)
                result[key] = mask_func(value)
            elif isinstance(value, dict):
                result[key] = cls.mask_dict(value)
            elif isinstance(value, list):
                result[key] = cls.mask_list(value)
            else:
                result[key] = value
        
        return result
    
    @classmethod
    def mask_list(cls, data: List) -> List:
        """递归脱敏列表中的敏感字段"""
        return [cls.mask_dict(item) if isinstance(item, dict) else item for item in data]
    
    @classmethod
    def mask_text(cls, text: str) -> str:
        """脱敏文本中的敏感信息"""
        # 脱敏邮箱
        text = cls._email_pattern.sub(lambda m: _mask_email(m.group()), text)
        
        # 脱敏手机号
        text = cls._phone_pattern.sub(lambda m: _mask_phone(m.group()), text)
        
        # 脱敏身份证号
        text = cls._id_card_pattern.sub(lambda m: _mask_id_card(m.group()), text)
        
        return text
    
    @classmethod
    def mask_sql_result(cls, result: Dict) -> Dict:
        """脱敏 SQL 查询结果"""
        # 对结果中的值进行脱敏
        if "rows" in result and isinstance(result["rows"], list):
            masked_rows = []
            for row in result["rows"]:
                if isinstance(row, (list, tuple)):
                    masked_rows.append([_mask_default(v) for v in row])
                elif isinstance(row, dict):
                    masked_rows.append(cls.mask_dict(row))
                else:
                    masked_rows.append(row)
            result["rows"] = masked_rows
        
        return result


def _mask_show_prefix(value: Any, prefix_len: int) -> str:
    """显示前缀，其余用 * 替代"""
    if value is None:
        return None
    value_str = str(value)
    if len(value_str) <= prefix_len:
        return "*" * len(value_str)
    return value_str[:prefix_len] + "*" * (len(value_str) - prefix_len)


def _mask_card(value: Any) -> str:
    """银行卡号脱敏：显示前4位和后4位"""
    if value is None:
        return None
    value_str = str(value).replace(" ", "").replace("-", "")
    if len(value_str) < 8:
        return "*" * len(value_str)
    return value_str[:4] + "*" * (len(value_str) - 8) + value_str[-4:]


def _mask_phone(value: Any) -> str:
    """手机号脱敏：显示前3位和后4位"""
    if value is None:
        return None
    value_str = str(value).replace(" ", "").replace("-", "")
    if len(value_str) != 11:
        return "*" * len(value_str)
    return value_str[:3] + "****" + value_str[-4:]


def _mask_email(value: Any) -> str:
    """邮箱脱敏：显示第一个字符@之前"""
    if value is None:
        return None
    value_str = str(value)
    if "@" not in value_str:
        return _mask_default(value_str)
    local, domain = value_str.split("@", 1)
    if len(local) <= 1:
        masked_local = "*"
    else:
        masked_local = local[0] + "*" * (len(local) - 1)
    return f"{masked_local}@{domain}"


def _mask_id_card(value: Any) -> str:
    """身份证号脱敏：显示前3位和后4位"""
    if value is None:
        return None
    value_str = str(value)
    if len(value_str) < 8:
        return "*" * len(value_str)
    return value_str[:3] + "*" * (len(value_str) - 7) + value_str[-4:]


def _default_mask(value: Any) -> str:
    """默认脱敏：显示第一个字符"""
    if value is None:
        return None
    value_str = str(value)
    if len(value_str) <= 1:
        return "*"
    return value_str[0] + "*" * (len(value_str) - 1)


def _mask_default(value: Any) -> str:
    """默认脱敏函数"""
    return _default_mask(value)


# 全局脱敏器实例
masker = SensitiveDataMasker()