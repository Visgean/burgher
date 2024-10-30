# Burgher - a static site generator focused on galleries

Burgher is a static site generator that makes it easy to create photo galleries from your existing folder structure. Instead of requiring you to reorganize your photos or maintain a separate structure, burgher works with how you already organize your photos.

Key features:
- Uses your existing photo folder organization
- Automatically generates thumbnails in multiple sizes
- Extracts and displays EXIF data
- Supports both single photos and gallery collections
- Simple template-based customization



# Example gallery 

Let's look at example structure of the gallery files:

```

.
├── Baltics
│   ├── Helsinki
│   │   ├── X-T5-2023-05-29 09.31.13.jpg
│   │   ├── X-T5-2023-05-30 19.24.16.jpg
│   │   ├── _Ruoholahti
│   │   │   ├── X-T5-2023-05-30 11.12.54.jpg
│   │   ├── _Suomenlinna
│   │   │   ├── X-T5-2023-05-29 11.05.40.jpg
│   │   │   └── X-T5-2023-05-29 11.54.06.jpg
│   │   └── info.md
│   ├── Lithuania
│   │   ├── _Countryside
│   │   │   ├── X-T5-2023-05-24 09.11.12.jpg
│   │   │   └── X-T5-2023-05-24 14.49.27.jpg
│   │   ├── _Druskininkai
│   │   │   └── X-T5-2023-05-22 08.43.41.jpg
│   │   ├── _Spit
│   │   │   ├── main.jpg
│   │   │   └── info.md
│   │   └── _Vilnius
│   │       └── main.jpg
│   └── Riga
└ ... 
```

Features:
- `main.jpg` is used as a cover image for the album
- `info.md` is used to provide description about the album
- `_` prefixed folders are treated as embedded albums - they get rendered as part of the main album but they can have their own `info.md` and cover image and they also get link on their own.
- Albums with `.hidden` empty file will not be indexed in the main page and will only be accessible with the main link


## How it works

1. Point burgher at your photo directories
2. Define your desired thumbnail sizes and template structure
3. Burgher automatically:
   - Creates optimized thumbnails
   - Extracts photo metadata
   - Generates gallery pages
   - Maintains your folder hierarchy

## Basic Usage

### Install 

```
    pip install burgher
```

### Create app.py:

```python
from pathlib import Path

from burgher.feed import Feed

from burgher import FrontMatterNode, StaticFolderNode, Gallery
from burgher import App

# this is the list of directories that will trigger rebuild of all template nodes
# if any file changes. 
check_paths = [
    Path("templates/"),
    Path("static/"),
]

out = Path("../build/")
PHOTO_DIR = Path("/home/user/photos/public/")
app = App(
    name="appname",
    template_dir="/templates",
    output_path=out,
    domain="http://example.com",
    check_paths=check_paths,
    # context db is json file that persists between builds
    # it is used to cache metadata for photos and other content to improve build performance
    context_db_path=Path("../example.json"),
)

app.register(
    # register directory with markdown files that will be rendered into html
    pages=FrontMatterNode.from_folder(
        "pages",
        template_name="page.html"
    ),
    # static files - these will be simply copied
    static=StaticFolderNode("static"),
    # register gallery, here we specify output file, so that the gallery is a root of the site
    gallery=Gallery(PHOTO_DIR,
                    output_file="index.html",
                    source_file="index.md"
                    ),
    rss=Feed(root_gallery=PHOTO_DIR),
)

# generate the site
app.generate()
```

and generate website via

```
    python app.py
```




## Available Node Types

### Basic Nodes

- `Node` - Base node class that others inherit from
- `StaticNode` - Copies a single file without modification 
- `StaticFolderNode` - Copies an entire folder structure without modification

### Content Nodes

- `BlogRoot` - Creates blog structure with listing index and page notes
- `TemplateNode` - Renders a Jinja2 template with context
- `MarkdownNode` - Renders markdown content into HTML
- `FrontMatterNode` - Markdown with YAML frontmatter for metadata


### Gallery and albums

- `Gallery` - Root node for the gallery
- `Album` - Folder with pictures or other albums
- `Picture` - Handles image files with EXIF data and metadata
- `Thumb` - Creates thumbnail versions of images



### Special Purpose Nodes

- `Feed` - Generates RSS/Atom feeds
- `Stats` - Generates statistics pages

Each node type can be configured with various options and composed together to build complex static sites. Nodes can have parent-child relationships and share context data.


## Node System and File Structure

The node system creates a graph that mirrors your site's file organization:

### Node Tree to File Tree Mapping

- Each `Node` corresponds to a file or directory in your site
- Parent nodes represent directories containing other files/folders
- Child nodes represent the contained files and subdirectories
- The node graph directly maps to the output file structure


### Context Database

The context database is used to cache metadata for photos and other content to improve build performance:

- Photo EXIF data is expensive to parse and extract from image files
- The context DB caches extracted metadata like:
  - Camera settings (aperture, shutter speed, ISO)
  - Camera/lens model information  
  - Dates and timestamps
  - Image dimensions
  - Other EXIF tags of interest

When building the site:

1. For each node, a hash based on file stats (size, modification time) is generated
2. If the hash exists in the context DB, cached metadata is used
3. If not found or the file changed, metadata is re-parsed and cached (e.g. EXIF data for photos)
4. For template nodes, content is regenerated if source files, templates, or Python code changes
5. This avoids re-processing unchanged files on subsequent builds

The context caching provides significant performance benefits:

- Only new/modified photos need full EXIF processing
- Cached metadata is instantly available for unchanged files
- Reduces build times dramatically for large photo galleries
- Preserves extracted metadata between builds

The context DB is stored as a JSON file that persists between builds. This allows incremental builds to be much faster than regenerating all metadata each time.


# Blog Root

For blogs there is a blog root node:

```python
from pathlib import Path

from burgher import App, BlogRoot, StaticFolderNode

blog_folder = Path('blog_entries')
check_paths = [
    Path("./templates/"),
    Path("./static/"),
]

blog = App(...)  # as before 
blog.register(
    index=BlogRoot(source_file=blog_folder / "index.md", post_folder=blog_folder / "posts"),
)

blog.generate()
```

This is the structure expected for the blog: 

```

.
├── index.md
└── posts
    ├── entry1.assets
    │   └── 2021-03-08 12.27.28.jpg
    ├── entry1.md
    └── xps-setup.md
```

The index has special markdown attributes: 

```markdown
---
title:  "Blog title"
title_post: "Blog"
go_back_title: "blog"
---

# Blog

Some info about the blog
```