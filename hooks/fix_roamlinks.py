"""
MkDocs hook: patch mkdocs-roamlinks-plugin.

Fixes two bugs:
1. os.walk() doesn't follow symlinks — when docs/ has symlinks
   to source directories, the plugin can't find any .md files.
2. Path-based wikilinks ([[path/to/file]]) resolve relative to
   docs_dir instead of the source page's directory, producing
   wrong relative URLs in the built HTML.
"""

import os
import mkdocs_roamlinks_plugin.plugin as rp


def _fix_rl_call(self, match):
    """Replacement for RoamLinkReplacer.__call__ with both bugs fixed.

    Bug 1 fix: os.walk(..., followlinks=True) — handled by os.walk patch.
    Bug 2 fix: os.path.join(abs_linker_url, rel_file) instead of
              os.path.join(self.base_docs_url, rel_file).
    """
    whole_link = match.group(0)
    filename = match.group(1).strip() if match.group(1) else ""
    title = match.group(2).strip() if match.group(2) else ""
    format_title = self.gfm_anchor(title)
    alias = match.group(3) if match.group(3) else ""
    width = match.group(4) if match.group(4) else ""
    height = match.group(5) if match.group(5) else ""

    # Absolute URL of the linker (page's source directory)
    abs_linker_url = os.path.dirname(
        os.path.join(self.base_docs_url, self.page_url))

    rel_link_url = ""
    if filename:
        if "/" in filename:
            if "http" in filename:
                rel_link_url = filename
            else:
                rel_file = filename
                # Check basename extension (not whole path - "../" has dots too)
                if "." not in os.path.basename(rel_file):
                    rel_file = filename + ".md"

                # BUGFIX: use abs_linker_url, not self.base_docs_url
                abs_link_url = os.path.dirname(os.path.join(
                    abs_linker_url, rel_file))
                rel_link_url = os.path.join(
                    os.path.relpath(abs_link_url, abs_linker_url),
                    os.path.basename(rel_file),
                )
                if title:
                    rel_link_url = rel_link_url + "#" + format_title
        else:
            # Simple filename wikilink — uses os.walk (patched for symlinks)
            for root, dirs, files in rp.os.walk(self.base_docs_url):
                for name in files:
                    if self.simplify(name) == self.simplify(filename):
                        abs_link_url = os.path.dirname(
                            os.path.join(root, name))
                        rel_link_url = os.path.join(
                            os.path.relpath(abs_link_url, abs_linker_url),
                            name,
                        )
                        if title:
                            rel_link_url = rel_link_url + "#" + format_title
        if rel_link_url == "":
            rp.log.warning(
                f"RoamLinksPlugin unable to find {filename} "
                f"in directory {self.base_docs_url}"
            )
            return whole_link
    else:
        rel_link_url = "#" + format_title

    rel_link_url = rel_link_url.replace("\\", "/")
    # Strip .md suffix so mkdocs renders a clean URL path
    if rel_link_url.endswith(".md"):
        rel_link_url = rel_link_url[:-3]
    # MkDocs page URLs are one level deeper than source file directories
    # (page.md → page/index.html). Adjust relative paths by prepending ../.
    if rel_link_url and not rel_link_url.startswith("#") and not rel_link_url.startswith("http"):
        rel_link_url = os.path.normpath("../" + rel_link_url)
    # Add trailing slash for directory-based URLs so GitHub Pages serves index.html
    if rel_link_url and not rel_link_url.endswith("/") and not rel_link_url.startswith("#"):
        if "/" in rel_link_url and "." not in os.path.basename(rel_link_url.split("#")[0]):
            rel_link_url += "/"

    if filename:
        if alias:
            link = f"[{alias}](<{rel_link_url}>)"
        else:
            link = f"[{filename + title}](<{rel_link_url}>)"
    else:
        if alias:
            link = f"[{alias}](<{rel_link_url}>)"
        else:
            link = f"[{title}](<{rel_link_url}>)"

    if width and not height:
        link = f'{link}{{ width="{width}" }}'
    elif not width and height:
        link = f'{link}{{ height="{height}" }}'
    elif width and height:
        link = f'{link}{{ width="{width}"; height="{height}" }}'

    return link


def on_pre_build(config, **kwargs):
    # Fix 1: os.walk in the roamlinks module follows symlinks
    original_walk = rp.os.walk

    def _walk_with_symlinks(*args, **kwargs):
        kwargs.setdefault("followlinks", True)
        return original_walk(*args, **kwargs)

    rp.os.walk = _walk_with_symlinks

    # Fix 2: Path-based wikilinks resolve relative to page dir, not docs_dir
    rp.RoamLinkReplacer.__call__ = _fix_rl_call
