import re
from html.parser import HTMLParser

from django.contrib.admin.views.decorators import staff_member_required
from django.http import Http404, HttpResponse

from content.models import BlogPost


class _HTMLToMarkdown(HTMLParser):
    """Lightweight HTML-to-Markdown converter for Wagtail RichText output.

    Handles the tag subset produced by Draftail: headings, paragraphs,
    bold/italic, links, lists, blockquotes, horizontal rules, line breaks.
    """

    def __init__(self):
        super().__init__()
        self._output = []
        self._tag_stack = []
        self._list_stack = []  # track nested ol/ul and ol counters
        self._href = None

    def handle_starttag(self, tag, attrs):
        self._tag_stack.append(tag)
        attrs_dict = dict(attrs)

        if tag in ("h1", "h2", "h3", "h4", "h5", "h6"):
            level = int(tag[1])
            self._output.append("\n" + "#" * level + " ")
        elif tag == "p":
            self._output.append("\n")
        elif tag in ("strong", "b"):
            self._output.append("**")
        elif tag in ("em", "i"):
            self._output.append("*")
        elif tag == "a":
            self._href = attrs_dict.get("href", "")
            self._output.append("[")
        elif tag == "ul":
            self._list_stack.append("ul")
        elif tag == "ol":
            self._list_stack.append(0)  # int counter for ordered lists
        elif tag == "li":
            indent = "  " * max(0, len(self._list_stack) - 1)
            if self._list_stack and isinstance(self._list_stack[-1], int):
                self._list_stack[-1] += 1
                self._output.append(f"\n{indent}{self._list_stack[-1]}. ")
            else:
                self._output.append(f"\n{indent}- ")
        elif tag == "blockquote":
            self._output.append("\n> ")
        elif tag == "br":
            self._output.append("  \n")
        elif tag == "hr":
            self._output.append("\n---\n")
        elif tag == "img":
            alt = attrs_dict.get("alt", "")
            src = attrs_dict.get("src", "")
            self._output.append(f"![{alt}]({src})")

    def handle_endtag(self, tag):
        if self._tag_stack and self._tag_stack[-1] == tag:
            self._tag_stack.pop()

        if tag in ("h1", "h2", "h3", "h4", "h5", "h6"):
            self._output.append("\n")
        elif tag == "p":
            self._output.append("\n")
        elif tag in ("strong", "b"):
            self._output.append("**")
        elif tag in ("em", "i"):
            self._output.append("*")
        elif tag == "a":
            self._output.append(f"]({self._href})")
            self._href = None
        elif tag in ("ul", "ol"):
            if self._list_stack:
                self._list_stack.pop()
            self._output.append("\n")
        elif tag == "blockquote":
            self._output.append("\n")

    def handle_data(self, data):
        self._output.append(data)

    def get_markdown(self):
        text = "".join(self._output)
        # Collapse excessive blank lines to at most two newlines
        text = re.sub(r"\n{3,}", "\n\n", text)
        return text.strip()


def html_to_markdown(html):
    """Convert an HTML string to Markdown."""
    parser = _HTMLToMarkdown()
    parser.feed(html)
    return parser.get_markdown()


@staff_member_required
def download_blog_post_markdown(request, page_id):
    try:
        page = BlogPost.objects.get(pk=page_id)
    except BlogPost.DoesNotExist:
        raise Http404

    # Build YAML frontmatter
    lines = [
        "---",
        f'title: "{page.title}"',
    ]
    if page.author:
        lines.append(f'author: "{page.author}"')
    if page.date:
        lines.append(f"date: {page.date.isoformat()}")
    lines.append("---")
    lines.append("")

    # Convert StreamField body to Markdown
    for block in page.body:
        if block.block_type == "paragraph":
            html = block.value.source
            lines.append(html_to_markdown(html))
            lines.append("")
        elif block.block_type == "image_gallery":
            title = block.value.get("title")
            if title:
                lines.append(f"### {title}")
                lines.append("")
            for item in block.value.get("images", []):
                image = item.get("image")
                caption = item.get("caption")
                if image:
                    alt = image.title if image.title else ""
                    url = image.get_rendition("original").url
                    lines.append(f"![{alt}]({url})")
                    if caption:
                        caption_text = html_to_markdown(caption.source)
                        lines.append(f"*{caption_text}*")
                    lines.append("")

    content = "\n".join(lines)
    response = HttpResponse(content, content_type="text/markdown")
    response["Content-Disposition"] = f'attachment; filename="{page.slug}.md"'
    return response
