from django.contrib import admin
from .models import Problem, TestCase, Submission, Post

# 注册题目表，并配置要在列表中展示的列
@admin.register(Problem)
class ProblemAdmin(admin.ModelAdmin):
    list_display = ('id', 'title', 'time_limit', 'memory_limit')
    search_fields = ('title',)

# 注册帖子表
@admin.register(Post)
class PostAdmin(admin.ModelAdmin):
    list_display = ('id', 'title', 'author', 'problem', 'created_at')
    list_filter = ('created_at',)

# 普通注册
admin.site.register(TestCase)
admin.site.register(Submission)

# 修改后台网页的标题和头
admin.site.site_header = '🚀 Geek OJ 全栈管理后台'
admin.site.site_title = 'Geek OJ Admin'