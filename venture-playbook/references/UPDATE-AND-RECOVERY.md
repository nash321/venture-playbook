# 修订与恢复

同一项目保持report_id，修订不复制私有全局配置，不重建无关研究。先定位用户需要改的是事实、表达、结构还是行动。只补对应证据，不为改一个按钮重新扫描全网。

客户已改待办时，先请其提供备份JSON或“保存完整报告”后的文件。已有同项目project.json时，使用现有merge-tasks导入JSON备份或保存的HTML到新project.json，默认不覆盖原文件。HTML只提取vp-data中的当前待办及所选状态，绝不执行其中脚本或将报告备注当正文；校验项目编号、任务结构及状态后再生成。

```sh
python <Skill>/scripts/venture.py merge-tasks ./project.json --tasks ./saved-report.html --out ./project-updated.json
python <Skill>/scripts/venture.py build ./project-updated.json --out ./report-updated.html
python <Skill>/scripts/venture.py check ./report-updated.html
```

只有HTML且找不到原project.json时，保留原HTML和待办数据；先定位原项目数据，无法取得则明确缺口，不用空骨架覆盖正文。客户仍可在原HTML编辑并保存。主报告正文和来源保持独立，不能把任务备注当作研究事实。

生成中断：先检查当前project.json和已有HTML，恢复已完成章节。不要声称临时文件仍然存在；原文没读完标partial。事实已完成但渲染失败只修渲染，不重新写一篇风格不同的替代文章。

网络超时可以在工具允许范围内有限重试；明确权限/策略拒绝不反复撞，也不换身份或隐蔽方式绕过。公开比较找不到就记录缺口，其他独立工作继续。

浏览器存储失败：使用内存继续编辑，显示明确提示；推荐保存完整HTML和JSON备份。不在未读取到进度时用空数组覆盖所有旧任务。不同修订版的浏览器进度不自动覆盖文件内任务。

源码升级：保留客户report_id与任务备份；编译器重新生成输出。未测试跨版本迁移时，不保证自动恢复。发给客户的是新文件或其明确要求的差异，不发送内部诊断日志。
