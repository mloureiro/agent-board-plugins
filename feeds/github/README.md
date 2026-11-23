# mloureiro:github

Turns the pull requests a GitHub search finds into board tasks. One action, `list-pull-requests`, gives one item per pull request.

## Prerequisites

- `python3` 3.9 or newer.
- [`gh`](https://cli.github.com), logged in (`gh auth login`), with access to the repositories you search.

Both must be on the `PATH` the board's units run with, which is shorter than a terminal's. `board doctor` runs this integration's `doctor` under that `PATH` and tells you what is missing.

The program only reads: it makes one GraphQL search through `gh api graphql --paginate`. It never comments, reviews or changes a pull request.

## Options

| Option | Type | Meaning |
| --- | --- | --- |
| `query` | text, 1 to 256 characters, required | A [GitHub search](https://docs.github.com/en/search-github/searching-on-github/searching-issues-and-pull-requests), such as `is:open draft:false review-requested:@me`. `is:pr` is added when the query has none. |
| `repositories` | list of 1 to 50 `owner/name`, optional | Each one adds `repo:owner/name` to the search. |
| `settleMinutes` | whole number, 0 to 120, default 10 | A pull request whose head commit is younger than this waits in Todo until it is that old. `0` turns the wait off. |

## Fields

A prompt may use `{url}`, `{title}`, `{updatedAt}`, `{status}` and `{labels}`, and the board's own `{key}`, `{title}` and `{version}`. Prefer `{url}`: a title is text someone else wrote.

| Field | Holds |
| --- | --- |
| `url` | The pull request's link. |
| `title` | The pull request's own title. |
| `updatedAt` | When it last changed, as an ISO time. |
| `status` | `draft`, `open`, `changes-requested` or `approved`. |
| `labels` | Its labels, comma-separated. |

The task's title is `owner/name#number` followed by the pull request's title. No author, description or comment is passed on. Text from GitHub has control characters and backslashes turned into spaces, and runs of spaces cut to one.

## When a task is requeued

The item's version is the head commit, followed by `@` and the time of the latest review request when there is one. A push, or a review that is requested again, changes the version: the board puts the task back in Todo instead of making a second one, and resumes the same session with the feed's `prompts.update`. A task that never ran starts fresh from `prompts.new`.

`settleMinutes` keeps a review from starting in the middle of a series of pushes. While the head commit is younger than the setting, the item carries a `notBefore` time and the task waits in Todo.

## Example

[feed.example.json](feed.example.json) is a feed entry. After installing the marketplace (see the repository's README), add it with

```sh
board feeds add gh-reviews feeds/github/feed.example.json
board doctor
board feeds run gh-reviews
```

Edit `repositories`, `dir`, `agent` and `lane` first. `dir` must be one of the directories `board dirs` lists.

## Moving from `github-reviews.sh`

1. Stop the timer that runs `github-reviews.sh`, so the two do not both make tasks.
2. Add the feed.

Each open review request gets one more task, once: the feed's keys (`feed:<name>:<url>`) differ from the script's, so the board sees them as new. Close the script's tasks that are still waiting. Tasks that already ran stay as they are.
