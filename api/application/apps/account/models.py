from tortoise import models, fields


class User(models.Model):
    id = fields.IntField(pk=True, generated=True, description="主键ID")
    username = fields.CharField(max_length=128, description="用户名")
    email = fields.CharField(max_length=128, unique=True, description="邮箱")
    password = fields.CharField(max_length=128, null=True, description="密码")
    is_active = fields.BooleanField(default=True, description="是否激活")
    token = fields.CharField(max_length=256, null=True, description="用户令牌")


    class Meta:
        table = "user"

    def __str__(self):
        return self.username
