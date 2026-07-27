# Video clip database

This Python TUI application manages a database of video snippets. It allows the user to create new
snippets using an IPC-connected mpv media player instance. It can also be used to generate web pages
and reports of the snippet database.

## Data model

TABLE clip
clip_id text primary key -- 7-digit random string, example af5c68d
scene_id text not null -- foreign ref to scene table
start_ts text not null -- video timestamp trim start
end_ts text not null -- video timestamp trim end
screenshot_ts text not null -- video timestamp of preview frame
source_filename text not null -- source filename without directory path
source_dir text -- directory path location of source file
source_hash text not null -- hash generated from partial content of source file
source_size int not null -- source file size in bytes
active bool not null default true -- toggle content visibility and video and screenshot image generation
created timestamp default now() not null -- creation time of this database row

TABLE scene
scene_id text primary key -- 4-digit scene id, example A7BN
title text
category text not null default 'C'
rating int 0...100
description text
imdb_url text
links text -- list of urls
metadata text
created timestamp default now() not null -- creation time of this database row

TABLE actor
actor_id int primary key autoincrement
name text not null
rating int 0...100
intro text
image_file_1 text -- filename of "profile pic"
image_file_2 text -- filename of secondary pic
imdb_url text
links text -- list of urls
metadata text
created timestamp default now() not null -- creation time of this database row

TABLE actress
actress_id int primary key autoincrement
name text not null
rating int 0...100
intro text
image_file_1 text -- filename of "profile pic"
image_file_2 text -- filename of secondary pic
imdb_url text
links text -- list of urls
metadata text
created timestamp default now() not null -- creation time of this database row

TABLE scene_actor
scene_id text composite primary key
actor_id int composite primary key
created timestamp default now() not null -- creation time of this database row

TABLE scene_actress
scene_id text composite primary key
actress_id int composite primary key
created timestamp default now() not null -- creation time of this database row

## Directory layout

The directory layout of 'pd' is below. `pd init` creates a new database and the directory structure
in the current folder. 'pd' will not operate in the current directory unless it is initialized, i.e.
the database pd.sqlite can be found.

```
│   pd.sqlite
├───content
│   │   C.html
│   │   index.html
│   ├───image
│   │   ├───actors
│   │   ├───actresses
│   │   └───screenshots
│   ├───thumbnails
│   └───video
├───report
└───trash
    ├───screenshots
    └───video
```

## Features

### Data capture

The user will work in mpv media player to seek the desired three time points for their clip.
Once all three time points have been registered:
    - a new scene id is generated in Python. Regenerate on collision.
    - the source media hash is computed with a specific algorithm that looks at part of the content.
    - a 7-digit clip id is generated in Python, similar to git short hash. Regenerate on collision.
    - a scene row is created, populating scene_id, category ('C') and creation timestamp
    - a clip row is created, populating clip_id, scene_id, start_ts, end_ts, screenshot_ts,
      source_filename, source_dir, source_hash, source_size, active (true) and creation
      timestamp
    - a preview screenshot is generated at screenshot_ts. Preview screenshot image naming: <scene_id>_<seq>_<clip_id>.jpg example: A7BN_001_af5c68d.jpg, where seq is clip rank within scene, ordered by clip creation timestamp, oldest first.
    - the user is presented with the "scene" UI view to modify scene title, category, rating, description,
      imdb_url, the list of links and add actors and actresses.

### UI

The UI consists of three views: "list", "scene" and "create".

**List tab**

A dual-pane view. On the left pane, a browsable list of all scenes, on the right a browsable list of
all clips associated with the currently highlighted scene. Left and right arrow keys or 'h', 'l' or tab to switch panes. Up and down arrow keys or 'j', 'k' to browse. To browse faster, PgUp, PgDown and the vim keys ctrl+u, ctrl+d and ctrl+f, ctrl+b also work.

- Activating a scene item on the left pane by pressing enter opens the scene in the "scene" view.
- Pressing 'p' on the left pane opens the latest associated clip where active=true in mpv at
  start_ts. If none of the clips has active=true or there are no clips, an error modal will be displayed.
- Activating a clip in the right pane by pressing enter will toggle its 'active' boolean.
- Pressing 'i' in the right pane opens a modal allowing the user to change that clip's scene_id.
- Pressing 'p' on the right pane opens the highlighted clip in mpv at start_ts.

**Create tab**

The "create" view initially displays message "Press 'p' to start player." unless an IPC-managed mpv
instance is already open. When mpv is open, the following information will be displayed: opened
filename and the current time index (example 13:13.986). Also displayed are the three video
timestamps this view is used to capture: start, end and screenshot. Keys:

- 'i' to set start_ts to the current time index in mpv
- 'o' to set end_ts to the current time index in mpv
- 's' to set screenshot_ts to the current time index in mpv

When all three timestamps are registered, the process described in the "Data capture" section will
take place and the "scene" modal view opens for the newly created scene. Before creation of a new
scene, the following rules must be satisfied:

- start_ts < end_ts
- start_ts <= screenshot_ts <= end_ts

The timestamps will reset when the file opened in mpv changes or mpv is closed and after creation of
a new scene.

**Scene view**

A full-screen modal view with a four-pane layout. On left, the main pane, to the right of it two stacked
panes for lists of actors and actresses. On the bottom, a reduced height pane for list of links
associated with the scene. Pressing '+' on any of the list views allows creation of new items using
a modal. For actors and actresses, only name input is required. For links, only url input is
required. Pressing 'd' on any list view item deletes it. The main pane allows editing of scene title, category, rating, imdb_url and description. Pressing <esc> closes the full-screen modal and returns to the currently active tab. Tab to cycle between panes. Keys for browsing inside list views same as defined for the List tab. To navigate between editable items in the main pane, up and down arrow keys or 'j', 'k' can be used. Enter activates an editable item opening a modal for editing contents.

- If an actor or actress with that name does not exist upon addition, a new database entry will be created.
- The 'links' list pane allows reordering of items by pressing ctrl+up, ctrl+down or ctrl+j, ctrl+k.

The application shall save modified data proactively without requiring the user to remember to save.

### Sync

The 'sync' operation can be triggered on the command line: 'pd sync'. It updates the generated
screenshot images and videos to match database contents.

- "Current clip" of each scene is the latest clip by 'created' where active=true.
- Based on information in the filenames, if the screenshot or video for the current clip does not
  exist, it will be
    - restored from the 'trash' directory if it exists there
    - otherwise generated using the 'vidclip' tool: `vidclip trim <input_path> <output_path> --start <start_ts> --end <end_ts> --copy`. If the input is not suitable for an mp4 container, the --copy flag is omitted. Output video file naming: <scene_id>_<seq>_<clip_id>.mp4 example: A7BN_001_af5c68d.mp4
- Any existing video and screenshot that is not from the "current clip" of scene will be moved into
  the trash directory.

### Site

Command line: `pd site [--category=<category>]`

Generates a static html page with a detailed listing and thumbnails of all scenes.

- synchronizes the thumbnails folder so that reduced size images of everything in the screenshots
  folder exist. Deletes extra thumbnails to match screenshots.
- lists all scenes in a simple html page.
    - clicking on thumbnail opens full size image
    - clicking on filename opens video for viewing in browser
    - information displayed: video filename, scene title, scene category, scene rating, imdb_url, clip source filename, clip source hash, scene creation time, scene description, scene links

### Report

Command line: `pd report`

- Number of scenes, actors and actresses
- Number of files in the 'video' directory and total size
- Number of files in the 'screenshots' directory and total size
- Number of videos and screenshots in the 'trash' directory and total trash size
- Distribution of clip durations where active = true
    - <= 10s
    - > 10s and <= 20s
    - > 20s and <= 30s
    - > 30s and <= 40s
    - > 40s and <= 50s
    - > 50s and <= 60s
    - > 60s
- Overlapping clips with different scene_id
- Scenes having 0 clips or more than 1 clips where active = true
