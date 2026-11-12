"""离线样本站：模拟公路施工封闭公告的同站分页列表与详情页。

数据全部内置，无外部依赖，供采集 API 离线联调。
页面结构与真实公告站点同构：
- /announcements?page=N     列表页（含“下一页”同站分页）
- /announcement/<id>        详情页（路段/方向/生效日期/每周封闭日/起止钟点）
- /maintenance              维护页：HTTP 200 但缺少公告目录结构（首页维护场景）
- /paged-maintenance?page=N 第 1 页为合法目录、翻到第 2 页返回维护页（后续页维护场景）
- /announcements-empty      合法空目录：保有表格结构但没有任何公告行
- 故意提供一个失效链接，用于验证“采集失败 -> 无法判定”的处理。
"""
from __future__ import annotations

from datetime import date
from flask import Flask, abort, render_template_string, request

app = Flask(__name__)

LIST_TEMPLATE = """
<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8"><title>施工封闭公告列表</title></head>
<body>
<h1>公路施工封闭公告</h1>
<table class="announcement-table">
  <thead><tr><th>公告标题</th><th>发布日期</th></tr></thead>
  <tbody>
  {% for item in items %}
    <tr>
      <td><a href="{{ item.href }}">{{ item.title }}</a></td>
      <td>{{ item.published }}</td>
    </tr>
  {% endfor %}
  </tbody>
</table>
<div class="pagination">
  {% if prev_href %}<a rel="prev" href="{{ prev_href }}">上一页</a>{% endif %}
  {% if next_href %}<a rel="next" href="{{ next_href }}">下一页</a>{% endif %}
</div>
</body></html>
"""

# 维护页：站点有时以 HTTP 200 返回，页面不含任何公告目录结构。
MAINTENANCE_TEMPLATE = """
<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8"><title>系统维护中</title></head>
<body>
<div class="maintenance-notice">
  <h1>系统维护中</h1>
  <p>公告系统正在升级维护，预计 22:00 至次日 06:00 暂停访问，请稍后再试。</p>
  <p>给您带来不便，敬请谅解。</p>
</div>
</body></html>
"""

DETAIL_TEMPLATE = """
<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8"><title>{{ ann.title }}</title></head>
<body>
<article class="content">
  <h1>{{ ann.title }}</h1>
  <p>路段编号：{{ ann.road_id }}</p>
  <p>方向：{{ ann.direction }}</p>
  <p>生效日期：{{ ann.effective_text }}</p>
  <p>封闭日：{{ ann.weekday_text }}</p>
  <p>封闭时间：{{ ann.clock_text }}</p>
  <p>管制措施：施工期间该路段禁止车辆通行，请提前绕行。</p>
</article>
</body></html>
"""

ANNOUNCEMENTS = [
    {
        "id": "gg-2026-001",
        "title": "G15沈海高速K123段下行夜间施工封闭公告",
        "published": "2026-11-01",
        "road_id": "G15-K123",
        "direction": "下行",
        "effective_start": date(2026, 11, 1),
        "effective_end": date(2026, 11, 30),
        "effective_text": "2026年11月1日至2026年11月30日",
        "weekday_text": "每周一、周三",
        "clock_text": "22:00 至 次日 05:00（跨午夜，归属当日封闭）",
    },
    {
        "id": "gg-2026-002",
        "title": "G15沈海高速K123段上行白天施工封闭公告",
        "published": "2026-11-02",
        "road_id": "G15-K123",
        "direction": "上行",
        "effective_start": date(2026, 11, 5),
        "effective_end": date(2026, 11, 25),
        "effective_text": "2026年11月5日至2026年11月25日",
        "weekday_text": "每周二、周四",
        "clock_text": "09:00 至 16:30",
    },
    {
        "id": "gg-2026-003",
        "title": "G25长深高速K88段双向周末施工封闭公告",
        "published": "2026-11-03",
        "road_id": "G25-K88",
        "direction": "双向",
        "effective_start": date(2026, 10, 15),
        "effective_end": None,
        "effective_text": "2026年10月15日起长期有效",
        "weekday_text": "每周六、周日",
        "clock_text": "00:00 至 24:00（全天封闭）",
    },
]

PAGE_SIZE = 2
# 故意放在列表里的失效链接，验证采集失败处理
BROKEN_HREF = "/announcement/gg-2026-deleted"


def _all_items() -> list[dict]:
    items = [
        {"href": f"/announcement/{a['id']}", "title": a["title"], "published": a["published"]}
        for a in ANNOUNCEMENTS
    ]
    items.insert(1, {"href": BROKEN_HREF, "title": "【已撤销】临时管制公告", "published": "2026-11-04"})
    return items


def _render_listing(items, page, has_next, *, path="/announcements"):
    """渲染列表页；分页链接显式传入，便于不同路由指向不同的后续页。"""
    prev_href = f"{path}?page={page - 1}" if page > 1 else None
    next_href = f"{path}?page={page + 1}" if has_next else None
    return render_template_string(
        LIST_TEMPLATE, items=items, prev_href=prev_href, next_href=next_href
    )


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/announcements")
def listing():
    page = max(1, request.args.get("page", default=1, type=int))
    items = _all_items()
    start = (page - 1) * PAGE_SIZE
    page_items = items[start : start + PAGE_SIZE]
    if not page_items and page != 1:
        abort(404)
    has_next = start + PAGE_SIZE < len(items)
    return _render_listing(page_items, page, has_next)


@app.get("/announcements-empty")
def empty_listing():
    """合法空目录：保有公告表格结构，但没有任何公告行，应允许判为空目录。"""
    return _render_listing([], page=1, has_next=False)


@app.get("/maintenance")
def maintenance():
    """首页维护：以 HTTP 200 返回维护页，页面缺少公告目录结构。"""
    return render_template_string(MAINTENANCE_TEMPLATE)


@app.get("/paged-maintenance")
def paged_maintenance():
    """后续页维护：第 1 页是合法目录并带“下一页”，第 2 页返回 HTTP 200 维护页。"""
    page = max(1, request.args.get("page", default=1, type=int))
    if page >= 2:
        return render_template_string(MAINTENANCE_TEMPLATE)
    items = _all_items()
    page_items = items[: PAGE_SIZE]
    # 显式让“下一页”指向仍返回维护页的第 2 页
    next_href = "/paged-maintenance?page=2"
    return render_template_string(
        LIST_TEMPLATE, items=page_items, prev_href=None, next_href=next_href
    )


@app.get("/announcement/<ann_id>")
def detail(ann_id: str):
    ann = next((a for a in ANNOUNCEMENTS if a["id"] == ann_id), None)
    if ann is None:
        abort(404)
    return render_template_string(DETAIL_TEMPLATE, ann=ann)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
