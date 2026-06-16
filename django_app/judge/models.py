from django.db import models
from django.contrib.auth.models import User

class Problem(models.Model):
    """题目表"""
    title = models.CharField(max_length=200, verbose_name="题目名称")
    description = models.TextField(verbose_name="题目描述", null=True, blank=True)
    time_limit = models.IntegerField(default=1000, verbose_name="时间限制(ms)")
    memory_limit = models.IntegerField(default=256, verbose_name="内存限制(MB)")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="创建时间")

class TestCase(models.Model):
    problem = models.ForeignKey(Problem, on_delete=models.CASCADE, related_name='cases')
    input_data = models.TextField(help_text="测试输入数据")
    expected_output = models.TextField(help_text="期望的正确输出数据")

    def __str__(self):
        return f"{self.problem.title} - 测试点 {self.id}"

class Submission(models.Model):
    """代码提交记录表"""
    STATUS_CHOICES = (
        ('PENDING', '等待评测'),
        ('JUDGING', '评测中'),
        ('AC', '答案正确 (Accepted)'),
        ('WA', '答案错误 (Wrong Answer)'),
        ('TLE', '运行超时 (Time Limit Exceeded)'),
        ('MLE', '内存超限 (Memory Limit Exceeded)'),
        ('CE', '编译错误 (Compile Error)'),
    )

    user = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name="提交者",
                             db_index=True)
    problem = models.ForeignKey(Problem, on_delete=models.CASCADE, verbose_name="题目",
                                db_index=True)
    code = models.TextField(verbose_name="源代码")
    language = models.CharField(max_length=20, default="python3", verbose_name="语言")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING',
                              verbose_name="状态", db_index=True)
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="提交时间",
                                      db_index=True)

    class Meta:
        indexes = [
            # 覆盖 dashboard 趋势查询: WHERE created_at >= ... GROUP BY date
            models.Index(fields=['created_at']),
            # 覆盖 ranking 查询: WHERE status='AC' GROUP BY user
            models.Index(fields=['status', 'user']),
            # 覆盖 overview distinct queries
            models.Index(fields=['status']),
        ]

    def __str__(self):
        return f"{self.user.username} - {self.problem.title} - {self.status}"

class Post(models.Model):
    title = models.CharField(max_length=200, verbose_name="帖子标题")
    content = models.TextField(verbose_name="帖子内容")
    author = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name="作者")
    # 允许帖子绑定具体的题目（比如题解），null=True表示也可以发水贴
    problem = models.ForeignKey(Problem, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="关联题目")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="发布时间")

    class Meta:
        verbose_name = "社区帖子"
        verbose_name_plural = verbose_name

    def __str__(self):
        return f"[{self.author.username}] {self.title}"