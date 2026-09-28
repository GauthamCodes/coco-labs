# Milestone 0B — Phase 0 closure preparation (evidence)

Collected 2026-09-29 (IST) from the worktree `p0-consolidation-merge`, after
`git fetch jazzy2 --prune` and `git fetch origin`. Every table below was read
from git, the GitHub API or the filesystem in this session. Nothing in this
file has been executed against a remote: **no tag was created or pushed, no
branch deleted, no release published, no repository renamed or archived.**

## 1. Repository state

| ref | SHA | note |
|---|---|---|
| local `main` | `442bca0` | = the Milestone 0A commit |
| `jazzy2/main` (GauthamCodes/coco-robot-jazzy-2.0) | `442bca0` | pushed from this machine 2026-09-29 01:54:44 +0530 (remote-tracking reflog: "update by push"), after 0A closed; not by this session |
| ahead / behind | 0 / 0 | |
| `origin/main` (GauthamCodes/coco-robot-ros2, the old repo) | `34f151c` | no merge-base with `main` |
| merge commit | `232454d` | parents `b15d445` (main) and `917bc59` (p03c-consolidation) |
| `p03c-consolidation` | `917bc59` | local only; ancestor of `main` |
| `p0-consolidation-merge` | 0B commit on top of `442bca0` | local only; fast-forwards `main` |

## 2. Remote branches (13 on `jazzy2`; no tags on the remote)

"In main" = the tip is an ancestor of `main`. "Unique" = `git cherry main
<branch>` commits with no patch-equivalent in `main`.

| branch | tip | in main? | active worktree | purpose | proposed tag | proposed remote action |
|---|---|---|---|---|---|---|
| `c2nav43-integration` | `1425e6c` | yes | – | C2-NAV.43–47: `/cmd_vel_gated` fix integrated, depth fusion candidate | `archive/c2nav43-integration` | delete after tag |
| `c2nav48-return-deadlock` | `04f9711` | yes | – | C2-NAV.48: `local_costmap.robot_radius` 0.20 → 0.25 | `archive/c2nav48-return-deadlock` | delete after tag |
| `c2nav49-integration` | `d317d85` | yes | `.claude/worktrees/c2nav43-integration` | C2-NAV.49 colour matrix on 0.25 | `archive/c2nav49-integration` | delete after tag |
| `claude/docker-reproducibility` | `23f372c` | **no** (+10 unique) | `~/coco-infra-worktree` | container runtime: pinned image, clean-room harness, CI job | `archive/claude/docker-reproducibility` | **keep** — unmerged live work |
| `coco-clean-runtime` | `b32539e` | yes | – | no TurtleBot dependency; `setup_env.sh` path cleaning | `archive/coco-clean-runtime` | delete after tag |
| `isaac-compat-4x` | `20a9619` | **no** (+2 unique) | `.claude/worktrees/isaac-compat` | Isaac Sim 4.5 / 4.2 compatibility measurements (docs only) | `archive/isaac-compat-4x` | delete after tag (deferred work, ROADMAP §9) |
| `p02-browser-experience` | `8991249` | yes | – | P0.2 second pass | `archive/p02-browser-experience` | delete after tag |
| `p02-release-candidate` | `c40098f` | yes | – | P0.2 release candidate | `archive/p02-release-candidate` | delete after tag |
| `p03-episode-spec` | `b3c6598` | yes | `.claude/worktrees/p02-browser` | P0.3 stage B: EpisodeSpec | `archive/p03-episode-spec` | delete after tag |
| `p03c-episode-gazebo` | `dfcbc4b` | yes | `.claude/worktrees/episode-gazebo` | P0.3 stage C: episode spawns Gazebo; head recorded by the P03C matrix | `archive/p03c-episode-gazebo` | delete after tag |
| `worktree-c2nav0-diagnosis` | `1235502` | **no** (94 unique, 4 equivalent) | `.claude/worktrees/c2nav0-diagnosis` | C2-NAV.0–42 diagnosis history; the fix reached `main` by cherry-pick (6503cd5), not by merge | `archive/worktree-c2nav0-diagnosis` | delete after tag (the tag keeps all 94) |
| `worktree-p01-platform` | `921f6d0` | yes | `.claude/worktrees/p01-platform` | P0.1 platform | `archive/worktree-p01-platform` | delete after tag |
| `main` | `442bca0` | – | the main checkout | canonical | none | keep |

Deleting a remote branch does not touch a local branch or a worktree; a local
branch whose upstream is deleted only reports `[gone]`.

Local-only branches (not on the remote, so out of scope for the tags):
`codex/c2nav33-review-preserved` 1d17a13 (+67), `codex/c2nav34-odom-final`
5c7f597 (+78), `codex/c2nav34-odom-review` 8a7b090 (+67),
`codex/p02-hardening` bdc0882 (+14), `p03-isaac-backend` ffb3fc6 (+2, worktree
`~/coco-isaac-backend`), `p03d-autonomous-target-search` d220ab8 (+4, worktree
`~/coco-p03d-target-search`), `p03c-consolidation` 917bc59 (in main),
`p0-consolidation-merge` (in main after the fast-forward).

### Archive-tag commands — prepared, NOT run

```bash
cd "$HOME/ros2_ws(personal)/src/coco-robot-ros2"
git fetch jazzy2 --prune
tag() {  # branch, full sha, one-line purpose
  git tag -a "archive/$1" "$2" -m "Archive of jazzy2 branch '$1' at $2, tagged in COCO Lab Phase 0 (Milestone 0B). $3"
}
tag c2nav43-integration           1425e6c3a779f89546d814d286d1e979ec4d98aa "C2-NAV.43-47 integration. Contained in main."
tag c2nav48-return-deadlock       04f97117f3793edb44aaf2ed52f541985904cb08 "C2-NAV.48 robot_radius fix. Contained in main."
tag c2nav49-integration           d317d85ee6f1575c2620f4e467d7e322d0310bc0 "C2-NAV.49 colour matrix. Contained in main."
tag claude/docker-reproducibility 23f372c62811b5bef07d02b9f38234adc58d5fb3 "Container runtime. NOT in main (10 unique commits)."
tag coco-clean-runtime            b32539ef5d551548e12a8bdcaebe01fbf1c7700d "Clean runtime. Contained in main."
tag isaac-compat-4x               20a9619aac8124ed8aede7623250074b5eafd73e "Isaac 4.x compatibility. NOT in main (2 unique commits)."
tag p02-browser-experience        89912497497f9cd16909170e405997a6ae24ddff "P0.2 second pass. Contained in main."
tag p02-release-candidate         c40098f42aec7a6740dd271360768ef90123d316 "P0.2 release candidate. Contained in main."
tag p03-episode-spec              b3c65985de6aa68f4701687f9b35a51e04239595 "P0.3 stage B. Contained in main."
tag p03c-episode-gazebo           dfcbc4bad02e78530e7bcd683e4ffddff9d8e186 "P0.3 stage C. Contained in main."
tag worktree-c2nav0-diagnosis     12355022260684a8aa01633ae9f28615bc150e92 "C2-NAV.0-42 diagnosis history. NOT in main (94 unique commits)."
tag worktree-p01-platform         921f6d0bef1aaac4a890df3fb14efe04608dee02 "P0.1 platform. Contained in main."
git tag -l 'archive/*' --format='%(refname:short) %(*objectname:short)'   # check before pushing
git push jazzy2 'refs/tags/archive/*'                                     # needs approval
```

Remote deletions, only after the tags are pushed and only with approval:

```bash
git ls-remote --tags jazzy2 'archive/*'        # confirm every tag is on the remote first
git push jazzy2 --delete c2nav43-integration c2nav48-return-deadlock \
  c2nav49-integration coco-clean-runtime isaac-compat-4x \
  p02-browser-experience p02-release-candidate p03-episode-spec \
  p03c-episode-gazebo worktree-c2nav0-diagnosis worktree-p01-platform
# claude/docker-reproducibility and main are kept.
```

## 3. Platform name candidates

`gh api repos/GauthamCodes/<name>` as the authenticated owner: 404 = no
repository by that name (a renamed repository would answer 301). Search
counts are GitHub's repository search, `<name> in:name`, taken 2026-09-29.

| name | free under GauthamCodes | repos matching in name | exact-name repos (first 100) | spelling | says "robot/robotics" | names a platform rather than this robot |
|---|---|---|---|---|---|---|
| `cutaway-robotics` | yes | 0 | 0 | one hyphen, common words | yes | yes — the ROADMAP's "cutaway engine" metaphor |
| `coco-robot-lab` | yes | 0 | 0 | plain | yes | partly — keeps the robot's name |
| `robotlab-live` | yes | 0 | 0 | "robotlab" is a compound | yes | yes |
| `open-robotics-lab` | yes | 4 | 1 | plain | yes | yes; close to "Open Robotics" (the ROS organisation) |
| `botbench-lab` | yes | 0 | 0 | "botbench" is a coinage | informal ("bot") | yes; "bench" also reads as benchmark |
| `coco-lab` | yes | 271 | 4 | plain | no | partly; "COCO" collides with the MS COCO dataset |
| `nav-lab` | yes | 1,933 | 3 | plain | no (navigation only) | narrower than the plan (Labs 2–5 go beyond navigation) |
| `ros-lab` | yes | 1,660 | 19 | plain | ROS only | yes, but generic |

No name has been chosen, and the repository has not been renamed.

## 4. Fetch video migration — prepared, NOT published

**Current asset.**
- Repository GauthamCodes/coco-robot-ros2 — public, not archived, default
  branch `main` at `34f151c`, description "Full ROS 2 Humble + Gazebo
  simulation … Basis of my IEEE ICRM 2025 paper."
- Release `m6-fetch-demo`, "M6 fetch mission — end-to-end demo", published
  2026-08-07T00:18:47Z, Latest, not draft, not prerelease.
- Asset `coco_fetch_demo.mp4`, video/mp4, **8,805,381 bytes**, sha256
  `7a2f761e76535cafd4d83cb57ba5a2c57739e2bc16efc634074b48fddad45674`
  (downloaded and hashed this session), 4 downloads.
- URL `https://github.com/GauthamCodes/coco-robot-ros2/releases/download/m6-fetch-demo/coco_fetch_demo.mp4`.
- **This asset is the only copy:** no `coco_fetch_demo*.mp4` exists anywhere
  under `~`.
- The new repository has **no releases**.

**The only pointer to it** is `README.md:59` of this repo (the "Watch the
fetch mission end to end" link).

**Proposed destination** — the same tag name on this repo, at `9b1ed7f`
("docs: demo video, attribution line, and the Phase 0.5/0.6 checkpoint",
2026-08-07), the `main` commit that first linked the video:

```bash
gh release download m6-fetch-demo -R GauthamCodes/coco-robot-ros2 -p coco_fetch_demo.mp4 -D "$HOME/coco_video_migration"
sha256sum "$HOME/coco_video_migration/coco_fetch_demo.mp4"   # must be 7a2f761e…5674
gh release view m6-fetch-demo -R GauthamCodes/coco-robot-ros2 --json body --jq .body > "$HOME/coco_video_migration/notes.md"
gh release create m6-fetch-demo "$HOME/coco_video_migration/coco_fetch_demo.mp4" \
  -R GauthamCodes/coco-robot-jazzy-2.0 --target 9b1ed7f \
  --title "M6 fetch mission — end-to-end demo" --notes-file "$HOME/coco_video_migration/notes.md"
```

**README pointer change** (one line, after the asset exists and its hash is
checked):

```diff
-▶ **[Watch the fetch mission end to end](https://github.com/GauthamCodes/coco-robot-ros2/releases/download/m6-fetch-demo/coco_fetch_demo.mp4)**
+▶ **[Watch the fetch mission end to end](https://github.com/GauthamCodes/coco-robot-jazzy-2.0/releases/download/m6-fetch-demo/coco_fetch_demo.mp4)**
```

If the repository is renamed later, GitHub redirects the old URL.

**What would be archived:** GauthamCodes/coco-robot-ros2. Its `main` is 34f151c
("Fix README: remove incorrect hardware section"). It is the Humble / Gazebo
Classic predecessor with unrelated history, and holds the release above. The
proposed pointer is a banner **added to the top** of its README, not a
replacement. The repository description cites an IEEE ICRM 2025 paper, so the
existing README may be what that paper's readers land on:

```markdown
> **This repository is archived.** COCO continues as
> [GauthamCodes/coco-robot-jazzy-2.0](https://github.com/GauthamCodes/coco-robot-jazzy-2.0)
> (ROS 2 Jazzy, Gazebo Harmonic). The M6 fetch video is released there as
> `m6-fetch-demo`. The Humble / Gazebo Classic code below is kept as it was.
```

Then `gh repo archive GauthamCodes/coco-robot-ros2 --yes`. Archiving makes the
repository read-only, but its releases and assets stay downloadable. None of
this has been run.

## 5. Cleanup audit (Part G)

Sizes are `du -sb` apparent bytes, measured in this session before any action.

| candidate | size (B) | mtime | created by | git repo? | unique work? | referenced by | live process | class | action |
|---|---|---|---|---|---|---|---|---|---|
| `~/Downloads/Antigravity.tar.gz` | 172,322,487 | 2026-09-11 09:30 | browser download | no | **yes**: it holds the Antigravity **IDE** (Electron app `Antigravity-x64/antigravity`, 389 entries), and the IDE is installed nowhere (no binary, .deb, snap or .desktop). `agy` 1.2.12 (`~/.local/bin/agy`, `--version` exits 0) is the separate CLI | – | 0A log | `agy` (the CLI) running | **UNKNOWN** | retained — the only copy of the IDE |
| `.codex/worktrees/c2nav0-implementation` | 219,462,730 | 2026-09-29 00:37 | Codex | orphaned worktree: `.git` points to a pruned `.git/worktrees/` entry | 64 of 65 files changed after checkout are blobs in git history. **Not in git:** `.navbench/c2nav35/` (navigation2 1.3.11 source tarball, patched `nav2_amcl` overlays with `capture.hpp`, build/selftest logs) and one colcon log | `.codex/` is user-owned (LAB_PHASES standing approvals) | none | **ARCHIVE** | retained for the owner |
| `<repo>/tatus --short` | 19,011 | 2026-09-19 03:24 | a `less` save (`s`) of colour `git diff` output | untracked | records an abandoned 11-line CLAUDE.md stub pointing to AGENTS.md (blob `7f93a36`, dangling, in no commit) | – | none | **UNKNOWN** | retained |
| `/var/crash` | 120,765,102 (6 dumps) | 2026-09-29 00:31 | apport | – | three are COCO-stack crashes (component_container_isolated 2026-09-28 02:01, parameter_bridge 09-26, rviz2 09-26) | – | – | ruby3.2/eog/node DELETE; ROS dumps UNKNOWN | **removed at 02:05 by another agent session, not by this one** (see §6). Note: the directory is sticky and world-writable and the dumps were owned by `gautham`, so no sudo was needed |
| Brave cache `~/.cache/BraveSoftware` | 1,696,777,591 | 2026-09-11 | Brave | – | – | – | Brave running (PID 3747) | KEEP (for now) | retained: safe deletion cannot be established while it runs |
| `~/coco_consolidation_ws` | 5,127,285 | 2026-09-28 01:17 | colcon `--symlink-install` | no | none: 681 files, symlinks into `~/coco-p03c-consolidation` at `917bc59` (clean, ancestor of `main`), 0 dangling | 0A SESSION_LOG (as the environment of a 1959+7 test run) | none (`lsof`) | **DELETE** | **deleted by this session** |
| `~/coco_p03c_ws` | 4,292,602 | 2026-09-26 13:30 | colcon `--symlink-install` | no | none: symlinks into `.claude/worktrees/episode-gazebo` at `dfcbc4b` (clean, ancestor of `main`), 0 dangling | P0.3C SESSION_LOG reproduce block (which rebuilds it with `build_overlay.sh`) | none | DELETE | **removed by another agent session** before this one acted |

Found by the delta audit and not acted on:
- `/tmp/launch_params_*`: 837 files, 4,109,543 B, ROS-launch temp files from the 0A runs (575 dated 09-28, 262 dated 09-29), with no ROS stack live. **The permission classifier denied the deletion** as a shared-scratch sweep, so they remain. They are cleared at reboot, or the owner can remove them.
- `~/.local/bin/agy.1790537402769579119.old`: 218,132,688 B, dated 2026-09-19. This is `agy`'s previous self-update binary. It is tool-managed, so it was retained.

## 6. Concurrent activity during this session

While 0B ran:
- **Codex** (`codex resume`, PID 9146, plus the ChatGPT/Codex app) and **`agy`** (PID 9641) were running.
- Two interactive terminals were open (pts/3 in the repo, pts/7 in `~`).
- `docs/SESSION_LOG.md` in the main checkout was modified at 02:06:43, uncommitted, with a 129-line entry, "Milestone 0B-H — Canonical home/workspace cleanup". This session did not write it, and this commit does not include it.

What that entry records:
- It deleted eight overlays, including `~/coco_p03c_ws`, `~/c2nav48_overlay`, `~/coco_p02_overlay` and `~/coco_navigation_overlay`.
- It deleted four accidental colcon directories in `~`, six loose files and two duplicate downloads.
- It deleted all six `/var/crash` dumps.
- It lists `~/coco_consolidation_ws` as preserved ("active build overlay"). This session had already deleted that overlay, on the grounds in §5. It can be rebuilt with `scripts/build_overlay.sh ~/coco_consolidation_ws` from `~/coco-p03c-consolidation`.

The two logs must be merged when this branch lands.
