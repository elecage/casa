# orbitlib

## Working rules (must follow)

- Never use `cat` in the shell to view files. Use the Read tool.
- Always Read a file before you Edit it.
- Never use shell `grep`. Use the Grep tool or `rg`.
- Before creating any new file, search the repository first to confirm no
  equivalent exists.
- Never use `git add -A`, `git add --all`, or `git add .`. Stage files
  explicitly by path.
- Always run `git status` or `git diff` before `git commit`.
- Never create files with `echo ... > file`. Use the Write tool.
- Always run the test suite before committing.
