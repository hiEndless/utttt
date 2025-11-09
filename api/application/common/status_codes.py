# 状态码定义

class StatusCode:
    SUCCESS = 0  # 请求成功
    ERROR = 1  # 请求失败
    PARAM_ERROR = 1001  # 参数错误
    NOT_FOUND = 1002  # 资源未找到
    SERVER_ERROR = 1003  # 服务器内部错误
    VALIDATION_ERROR = 1004  # 数据验证错误
    DATABASE_ERROR = 1005  # 数据库操作错误
    
    # 状态码对应的消息
    MESSAGE = {
        SUCCESS: "请求成功",
        ERROR: "请求失败",
        PARAM_ERROR: "参数错误",
        NOT_FOUND: "资源未找到",
        SERVER_ERROR: "服务器内部错误",
        VALIDATION_ERROR: "数据验证错误",
        DATABASE_ERROR: "数据库操作错误"
    }
    
    @classmethod
    def get_message(cls, code):
        """获取状态码对应的消息"""
        return cls.MESSAGE.get(code, "未知错误")