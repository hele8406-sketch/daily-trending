import requests
import feedparser
import os
import re
import sys
from datetime import datetime

DEEPSEEK_API_KEY = os.environ.get("DEEPSEEK_API_KEY")
DEEPSEEK_API_URL = "https://api.deepseek.com/chat/completions"

# ===== 数据源配置 =====
# 对于支持官方 JSON 接口的，type 设为 "api"，url 填请求地址
# 其他平台仍走 RSSHub 备用实例
SOURCES = [
    {
        "name": "微博热搜",
        "type": "api",
        "url": "https://weibo.com/ajax/side/hotSearch"
    },
    {
        "name": "知乎热榜",
        "type": "api",
        "url": "https://www.zhihu.com/api/v3/feed/topstory/hot-lists/total?limit=20"
    },
    {
        "name": "B站热门",
        "type": "api",
        "url": "https://api.bilibili.com/x/web-interface/popular?ps=20"
    },
    {
        "name": "百度热搜",
        "type": "rsshub",
        "url": "https://rsshub.pseudoyu.com/baidu/top"
    },
    {
        "name": "抖音热点",
        "type": "rsshub",
        "url": "https://rsshub.pseudoyu.com/douyin/hot"
    },
    {
        "name": "头条热榜",
        "type": "rsshub",
        "url": "https://rsshub.pseudoyu.com/toutiao/hot"
    },
    {
        "name": "豆瓣小组精选",
        "type": "rsshub",
        "url": "https://rsshub.pseudoyu.com/douban/group/explore"
    },
    {
        "name": "贴吧热议",
        "type": "rsshub",
        "url": "https://rsshub.pseudoyu.com/tieba/hot"
    },
    {
        "name": "TikTok 热搜",
        "type": "rsshub",
        "url": "https://rsshub.pseudoyu.com/tiktok/hot"
    }
]

def fetch_weibo():
    """微博官方 JSON 接口"""
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
    try:
        resp = requests.get("https://weibo.com/ajax/side/hotSearch", headers=headers, timeout=10)
        data = resp.json()
        items = data.get("data", {}).get("realtime", [])
        trends = []
        for idx, item in enumerate(items[:20]):
            word = item.get("word", "")
            trends.append({
                "title": word,
                "link": f"https://s.weibo.com/weibo?q={requests.utils.quote(word)}",
                "summary": f"热搜第{idx+1}位"
            })
        print(f"  ✅ 已获取 {len(trends)} 条微博热搜")
        return trends
    except Exception as e:
        print(f"  ❌ 微博抓取失败: {e}")
        return []

def fetch_zhihu():
    """知乎官方热榜接口"""
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        resp = requests.get("https://www.zhihu.com/api/v3/feed/topstory/hot-lists/total?limit=20", headers=headers, timeout=10)
        data = resp.json()
        items = data.get("data", [])
        trends = []
        for item in items:
            # 知乎热榜 API 返回的结构，有时不同，需取 target 字段
            target = item.get("target", {})
            title = target.get("title", "")
            url = target.get("url", "")
            if not url:
                url = f"https://www.zhihu.com/question/{target.get('id', '')}"
            trends.append({"title": title, "link": url, "summary": f"热度: {item.get('detail_text', '')}"})
        print(f"  ✅ 已获取 {len(trends)} 条知乎热榜")
        return trends
    except Exception as e:
        print(f"  ❌ 知乎抓取失败: {e}")
        return []

def fetch_bilibili():
    """B站官方热门接口"""
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        resp = requests.get("https://api.bilibili.com/x/web-interface/popular?ps=20", headers=headers, timeout=10)
        data = resp.json()
        items = data.get("data", {}).get("list", []) or data.get("data", [])
        trends = []
        for item in items:
            title = item.get("title", "")
            bvid = item.get("bvid", "")
            trends.append({
                "title": title,
                "link": f"https://www.bilibili.com/video/{bvid}",
                "summary": f"播放量：{item.get('stat', {}).get('view', '')}"
            })
        print(f"  ✅ 已获取 {len(trends)} 条 B站热门")
        return trends
    except Exception as e:
        print(f"  ❌ B站抓取失败: {e}")
        return []

def fetch_rsshub(name, url):
    """通过 RSSHub 抓取（备用实例）"""
    try:
        feed = feedparser.parse(url, agent="Mozilla/5.0")
        trends = []
        for entry in feed.entries[:20]:
            trends.append({
                "title": entry.title,
                "link": entry.link,
                "summary": entry.get("summary", "")[:100] if hasattr(entry, "summary") else ""
            })
        print(f"  ✅ 已获取 {len(trends)} 条 {name}")
        return trends
    except Exception as e:
        print(f"  ❌ {name} 抓取失败: {e}")
        return []

def fetch_all_trends():
    """汇总：先官方接口，再 RSSHub"""
    all_trends = []
    # 先抓取有官方接口的平台
    all_trends.extend(fetch_weibo())
    all_trends.extend(fetch_zhihu())
    all_trends.extend(fetch_bilibili())
    # 再抓取 RSSHub 平台
    for src in SOURCES:
        if src["type"] == "rsshub":
            trends = fetch_rsshub(src["name"], src["url"])
            all_trends.extend(trends)
    return all_trends

# ---------- DeepSeek 整理与页面生成（同方案二，未改动）----------
def summarize_with_deepseek(trend_list):
    if not trend_list:
        return "<p>今日暂无热门数据。</p>"
    text = "\n".join([f"- [{t['title']}]({t['link']})（{t['summary']}）" for t in trend_list[:80]])
    prompt = f"""你是一个专业的内容编辑。请根据以下各平台热门话题列表，生成一份「今日全网热门话题速览」。
要求：
1. 挑选各平台最具代表性的 5-8 个话题进行介绍。
2. 按平台分类（微博、知乎、百度、B站、抖音、头条、豆瓣小组、贴吧、TikTok），每个平台下用列表展示话题名称和链接。
3. 每个话题一句话点评或简要说明（不超过30字）。
4. 顶部写一段100字以内的「今日热点总览」。
5. 输出严格 HTML 片段，不要包含 ```html``` 标记。
格式参考：
<p>【今日热点总览】……</p>
<h2>🔥 平台名</h2>
<ul>
  <li><a href="链接">话题名</a> – 简要说明</li>
  ...
</ul>
……

话题列表：
{text}"""
    headers = {"Authorization": f"Bearer {DEEPSEEK_API_KEY}", "Content-Type": "application/json"}
    data = {
        "model": "deepseek-chat",
        "messages": [
            {"role": "system", "content": "你是一个严谨的编辑，只输出HTML片段，不额外说明。"},
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.5,
        "max_tokens": 2500
    }
    print("  正在请求 DeepSeek API...")
    try:
        resp = requests.post(DEEPSEEK_API_URL, headers=headers, json=data, timeout=30)
        resp.raise_for_status()
        result = resp.json()
        if "choices" not in result:
            return "<p class='error'>AI 返回数据异常，请稍后重试。</p>"
        raw = result["choices"][0]["message"]["content"]
    except Exception as e:
        print(f"  ❌ DeepSeek 调用失败: {e}")
        return "<p class='error'>AI 服务暂时不可用。</p>"
    cleaned = re.sub(r'^```html\s*', '', raw, flags=re.IGNORECASE)
    cleaned = re.sub(r'\s*```$', '', cleaned)
    return cleaned.strip()

def build_html(summary_html):
    today = datetime.now().strftime("%Y年%m月%d日")
    update_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>每日热门话题 - {today}</title>
  <style>
    body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; max-width: 800px; margin: 0 auto; padding: 20px; background: #f7f9fc; }}
    .header {{ background: linear-gradient(135deg, #ff6b6b 0%, #feca57 100%); color: white; padding: 30px; border-radius: 12px; margin-bottom: 20px; }}
    .header h1 {{ margin: 0 0 10px 0; }}
    .header p {{ margin: 0; opacity: 0.9; }}
    .content {{ background: white; padding: 30px; border-radius: 12px; box-shadow: 0 2px 8px rgba(0,0,0,0.1); }}
    .content h2 {{ color: #ff6b6b; border-bottom: 2px solid #eee; padding-bottom: 8px; }}
    .content ul {{ padding-left: 20px; }}
    .content li {{ margin-bottom: 8px; line-height: 1.6; }}
    .content a {{ color: #ff6b6b; text-decoration: none; }}
    .content a:hover {{ text-decoration: underline; }}
    .footer {{ text-align: center; margin-top: 20px; color: #999; font-size: 14px; }}
    .error {{ color: red; font-weight: bold; }}
  </style>
</head>
<body>
  <div class="header">
    <h1>📈 全网热门话题速览</h1>
    <p>📅 {today} ｜ 基于 DeepSeek 自动整理 ｜ 每日 8:00 更新</p>
  </div>
  <div class="content">
    {summary_html}
  </div>
  <div class="footer">
    <p>🕒 最后更新：{update_time} (北京时间)</p>
    <p>数据来源：微博、知乎、百度、B站、抖音、头条、豆瓣小组、贴吧、TikTok | <a href="https://github.com">GitHub</a> 托管</p>
  </div>
</body>
</html>"""

def main():
    print(f"🚀 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} 启动热门话题收集...")
    if not DEEPSEEK_API_KEY:
        print("❌ 致命错误：DEEPSEEK_API_KEY 未设置！")
        sys.exit(1)
    trends = fetch_all_trends()
    print(f"📊 共获取 {len(trends)} 条话题")
    if len(trends) == 0:
        error_html = "<p class='error'>今日未能获取到任何热门话题，可能接口临时不可用，明日将自动重试。</p>"
        full_html = build_html(error_html)
    else:
        print("🧠 调用 DeepSeek 整理话题...")
        summary_html = summarize_with_deepseek(trends)
        print("🎨 构建完整页面...")
        full_html = build_html(summary_html)
    os.makedirs("docs", exist_ok=True)
    with open("docs/index.html", "w", encoding="utf-8") as f:
        f.write(full_html)
    print("✅ 热门话题页面已更新！")

if __name__ == "__main__":
    main()
