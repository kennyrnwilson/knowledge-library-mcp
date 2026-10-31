# Teaching through the knowledge-library MCP server

You are running the `teach` skill below, but not in Claude Code. The teaching
workspace is not your current directory. It is the folder
`05-projects/<project>/teach/` in the knowledge library, and you reach it only
through these tools:

- `teach_start(project)` — the skill, plus the workspace's current state. You
  have just called it.
- `write_teach_file(project, path, content)` — create or replace one workspace
  file. `path` is relative to the workspace, for example `lessons/0003-x.html`.
- `edit_teach_file(project, path, old, new)` — replace one exact, unique piece
  of text in a workspace file. Use it for small fixes instead of rewriting the
  whole file.
- `list_lessons(project)` and `get_lesson(path)` — the lessons so far, and a
  lesson's readable text.
- `save_changes(message)` — commit and push. Call it **only** when the user
  explicitly approves ("save it", "looks good"). Until then, the files are
  drafts on disk and nothing is published.

Where the skill and these rules differ, these rules win:

1. **Paths.** Read `./lessons/`, `./assets/` and the other workspace paths in
   the skill as paths inside the workspace, written with the tools above.
   `teach_start` already returned the workspace state, so do not ask for it
   again.
2. **Opening a lesson.** You cannot run a CLI command. After the user saves,
   give the lesson's published URL from `write_teach_file`. The site rebuilds a
   few minutes after the push.
3. **Allowed files.** `.html`, `.css`, `.js`, `.svg` and `.md` only. The site
   does not publish `.json`, so keep a component's data in a `.js` file.
4. **Links.** Link lessons, reference pages and assets with relative paths
   (`../assets/course.css`, `../reference/glossary.html`). Every lesson sets
   `<meta name="viewport" content="width=device-width, initial-scale=1">`: the
   user often reads on a phone.
5. **Sources.** Use web search to find and check sources. Do not teach from
   memory alone, as the skill says.
6. **Cost.** Write each file once, then use `edit_teach_file` for corrections.
   Read an existing lesson with `get_lesson` only when you need its content.
7. **A lesson plan.** If the workspace state has a `PLAN.md`, it is a book's
   lesson plan, drafted in the reading app. Teach the first lesson in it that is
   not yet a link, from the book's own text and chapter summaries. Use the
   section's "Read it" link as the primary source. After the user saves the
   lesson, turn its line in `PLAN.md` into a link to it with `edit_teach_file`.
