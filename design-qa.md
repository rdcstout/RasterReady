# Split layout and appearance verification

Status: passed for the macOS layout and appearance milestone; other-platform visual checks remain pending.

The retry/error footer and Qt-menu changes were checked in source renders at 900×700 in both themes and in signed Mac development bundles. Status text spans the footer above the actions, so validation errors remain readable when Prepare is visible. Native checks confirmed that queued files can be processed after correcting a project name without reselecting files. The later in-app notices viewer was checked in both themes, including search and selection. These development checks do not establish final installer acceptance.

The selected visual target is the third displayed GUI concept (Split Canvas). Implementation retains its settings sidebar, large drop canvas, results table, red primary action and sparse header. Light and Dark plus Follow system were explicitly required and are available without clearing the project or batch results.

Visual comparison used the selected source image and an actual Qt render together at a common scale. Native packaged app screenshots were separately inspected on an Apple Silicon Mac. The final rebuild was launched and Dark mode plus a checked enlargement control were visually verified; Light mode persistence on launch was observed. Persistent evidence is in the private project workspace, outside the public source tree. Generated concept images are references; implementation captures are actual Qt renders.

Corrected issues:

- Sidebar fields clipped by long preset contents: constrained combo sizing and checked project/preset geometry.
- Missing dropdown indicators: corrected Qt stylesheet resource paths; Fusion styling verified in the rebuilt native app, including visible dropdown arrows.
- Dark theme scrollbar inherited a light background: explicitly themed the scroll track and handle.

Intentional adaptations: precise fit/crop/padding controls and an enlargement checkbox replace the concept's ambiguous proportions switch. Sidebar guidance describes actual preset limitations. The output path is always Downloads/project name. Real results omit decorative thumbnails and unimplemented overflow actions. The appearance selector is new. Native window chrome is retained.

Checks: 1040x900 Light and Dark renders after a real three-file Sony RAW batch; 900x700 custom settings with scroll access; field bounds, drop-area height and footer visibility; keyboard theme selection; persisted appearance on reopen; native Command-Shift-L/D actions. Automated suite at the later hardening checkpoint: 98 tests passed. Source run uses Qt's Fusion style for the same controls on each target OS; native OS window chrome and file picker remain.

Release limitations: Windows/Linux native visual and packaged runtime checks are pending. This assessment covers the selected desktop layout and appearance milestone, not release readiness, screen-reader certification or all future features.

Drag-and-drop event checks cover a two-image batch with spaces/Unicode filenames and mixed local/remote URLs. Accepted imports explicitly report a copy operation even when the sender proposes moving; move-only, remote-only and disabled drops are rejected. Source images remain byte-identical and outputs contain no embedded metadata in the representative test. Native Finder-to-app drag delivery was not established by the automation and still needs platform acceptance; event-level tests do not substitute for that check.

Later native check on the development bundle built from c48ab43: Command-O selected a deliberately damaged JPEG, the result displayed Failed with the complete accessible error description, and Command-Shift-R followed by Return opened the full plain-text details dialog. OK dismissed it and a subsequent Command-Q exited; process absence was checked separately. Review results now use an amber warning icon alongside their text label. These checks do not establish Windows/Linux behavior.
