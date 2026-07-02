import os
src = r"C:\Users\LENOVO\Desktop\TestForge -  07011951 - hermes\backend\core\web_crawler.py"

with open(src, "r", encoding="utf-8") as f:
    original = f.read()

content = original

# 1. Playwright import
logger_line = 'logger = logging.getLogger("testforge")\n'
pw_block = (
    "\ntry:\n"
    "    from playwright.async_api import async_playwright\n"
    "    _has_playwright = True\n"
    "except ImportError:\n"
    "    _has_playwright = False\n"
    "    logger.warning(\"Playwright not installed; SPA mode unavailable\")\n"
    "\n"
)
content = content.replace(logger_line, logger_line + pw_block)

# 2. SPA constant
content = content.replace(
    "\nasync def crawl_website(",
    "\n_SPA_AUTO_DETECT_THRESHOLD = 3\n\nasync def crawl_website(",
)

# 3. Replace docstring
idx = original.find("async def crawl_website(")
lines = original[idx:].split("\n")
doc_lines = []
collecting = False
for line in lines[4:30]:
    stripped = line.strip()
    if stripped.startswith('"""'):
        if not collecting:
            collecting = True
            doc_lines.append(line)
        else:
            doc_lines.append(line)
            break
    elif collecting:
        doc_lines.append(line)
old_doc = "\n".join(doc_lines)
new_doc = (
    '    """BFS crawl with SPA auto-detection.\n'
    "\n"
    "    When the first page yields < _SPA_AUTO_DETECT_THRESHOLD\n"
    "    internal links, automatically switches to Playwright\n"
    "    browser rendering for subsequent pages.\n"
    "\n"
    "    Returns:\n"
    '        CrawlResult\n'
    '    """'
)
content = content.replace(old_doc, new_doc, 1)
print("Doc replaced:", "SPA" in content)

# 4. Add use_browser flags
needle = "allowed_domain = parsed_start.netloc\n\n    # robots.txt"
replacement = "allowed_domain = parsed_start.netloc\n    use_browser = False\n    detected_spa = False\n\n    # robots.txt"
content = content.replace(needle, replacement, 1)
print("Step 4:", "use_browser" in content)

# 5. SPA detection in batch
batch_needle = "                visited.add(url)\n                batch.append((url, depth))"
spa_insert = (
    "                visited.add(url)\n"
    "\n"
    "                # SPA auto-detect on first page\n"
    "                if not detected_spa and len(result.pages) == 0 and _has_playwright:\n"
    "                    sample = await _fetch_page(session, url, depth, semaphore)\n"
    "                    links_found = len(sample.internal_links)\n"
    "                    is_spa = (\n"
    "                        not sample.error\n"
    "                        and sample.status < 400\n"
    "                        and 'text/html' in sample.content_type\n"
    "                        and links_found < _SPA_AUTO_DETECT_THRESHOLD\n"
    "                    )\n"
    "                    if is_spa:\n"
    "                        use_browser = True\n"
    "                        detected_spa = True\n"
    "                        logger.info(\n"
    '                            "SPA detected (%d internal links), switching to Playwright",\n'
    "                            links_found,\n"
    "                        )\n"
    "                        visited.discard(url)\n"
    "                        batch.append((url, depth))\n"
    "                    else:\n"
    "                        result.pages.append(sample)\n"
    "                        if sample.error:\n"
    "                            result.failed_count += 1\n"
    "                        else:\n"
    "                            result.visited_count += 1\n"
    "                            result.max_depth_reached = max(result.max_depth_reached, depth)\n"
    "                        if sample.status >= 400:\n"
    "                            result.broken_links.append({\n"
    '                                "url": url, "status": sample.status,\n'
    '                                "parent": _find_parent(result.pages, url),\n'
    "                            })\n"
    "                        if not sample.error and depth < max_depth:\n"
    "                            for link in sample.internal_links:\n"
    "                                if link not in visited and _is_allowed(link, allowed_paths, visited):\n"
    "                                    queue.append((link, depth + 1))\n"
    "                    continue\n"
    "\n"
    "                batch.append((url, depth))"
)
content = content.replace(batch_needle, spa_insert, 1)
print("Step 5:", "SPA auto-detect" in content)

# 6. Browser rendering
exec_needle = (
    "            tasks = [\n"
    "                _fetch_page(session, url, depth, semaphore)\n"
    "                for url, depth in batch\n"
    "            ]\n"
    "            pages = await asyncio.gather(*tasks, return_exceptions=False)"
)
exec_replacement = (
    "            if use_browser:\n"
    "                for url, depth in batch:\n"
    "                    page = await _fetch_page_with_browser(url, depth, timeout)\n"
    "                    result.pages.append(page)\n"
    "                    if page.error:\n"
    "                        result.failed_count += 1\n"
    "                    else:\n"
    "                        result.visited_count += 1\n"
    "                        result.max_depth_reached = max(result.max_depth_reached, depth)\n"
    "                    if page.status >= 400:\n"
    "                        result.broken_links.append({\n"
    '                            "url": url, "status": page.status,\n'
    '                            "parent": _find_parent(result.pages, url),\n'
    "                        })\n"
    "                    if not page.error and depth < max_depth:\n"
    "                        for link in page.internal_links:\n"
    "                            if link not in visited and _is_allowed(link, allowed_paths, visited):\n"
    "                                queue.append((link, depth + 1))\n"
    "                pages = []\n"
    "            else:\n"
    "                tasks = [\n"
    "                    _fetch_page(session, url, depth, semaphore)\n"
    "                    for url, depth in batch\n"
    "                ]\n"
    "                pages = await asyncio.gather(*tasks, return_exceptions=False)"
)
content = content.replace(exec_needle, exec_replacement, 1)
print("Step 6:", "use_browser" in content)

with open(src, "w", encoding="utf-8") as f:
    f.write(content)

print("OK - written, lines:", len(content.split("\n")))
