# Complete Guide to Git Tagging and GitHub Releases

## Table of Contents
1. [Understanding Git Tags vs GitHub Releases](#understanding-git-tags-vs-github-releases)
2. [Tagging Best Practices](#tagging-best-practices)
3. [Creating Tags in PyCharm](#creating-tags-in-pycharm)
4. [Pushing Tags to GitHub](#pushing-tags-to-github)
5. [Creating GitHub Releases](#creating-github-releases)
6. [Troubleshooting](#troubleshooting)
7. [Internal vs Public Versioning Strategy](#internal-vs-public-versioning-strategy)

## Understanding Git Tags vs GitHub Releases

### Git Tags
- **Local tags**: Created in your repository (PyCharm, command line)
- **Remote tags**: Pushed to GitHub
- **Purpose**: Mark specific commits as important points in history

### GitHub Releases
- **Built on top of tags**: Each release is associated with a tag
- **Additional features**: Release notes, binary attachments, download statistics
- **Purpose**: Public distribution points for your software

**Important**: Tags created in PyCharm are LOCAL until explicitly pushed to GitHub!

## Tagging Best Practices

### Version Naming Convention (Semantic Versioning)

```
vMAJOR.MINOR.PATCH

v2.0.0
│ │ │
│ │ └── Patch: Bug fixes (backwards compatible)
│ └──── Minor: New features (backwards compatible)
└────── Major: Breaking changes

Examples:
v1.0.0 - Initial release
v1.0.1 - Bug fix
v1.1.0 - New feature
v2.0.0 - Breaking changes
```

### Tag Types

#### Release Tags (Public)
```bash
v1.0.0      # Stable release
v2.0.0      # Major release
v2.1.0      # Feature release
```

#### Pre-release Tags
```bash
v2.0.0-rc1   # Release candidate
v2.0.0-beta  # Beta version
v2.0.0-alpha # Alpha version
```

#### Internal Tags (Development)
```bash
dev-2025-01-15        # Development checkpoint
feature-complete-api  # Feature milestone
before-refactor       # Backup point
tested-production     # QA approved
```

## Creating Tags in PyCharm

### Method 1: Via Git Log (Recommended)

1. **Open Git Log**
   - View → Tool Windows → Git (Alt+9)
   - Or click Git tab at bottom

2. **Select the commit to tag**
   - Navigate to the specific commit in the log
   - Right-click on the commit

3. **Create the tag**
   - Select "New Tag..."
   - Enter tag name: `v2.0.0`
   - Enter message: `Version 2.0.0 - Enhanced with rate limiting`
   - Click "Create Tag"

### Method 2: Via VCS Menu

1. **Open tag dialog**
   - VCS → Git → New Tag...
   - Or Git → New Tag... (newer PyCharm)

2. **Configure tag**
   - Tag name: `v2.0.0`
   - Message: Your release description
   - Commit: Select specific commit or HEAD

### Method 3: Via Branch Widget

1. **Click branch name** (bottom-right corner)
2. **Click "+ New Tag"**
3. **Enter tag details**

### ⚠️ Critical Step: Push Tags to GitHub

**Tags created in PyCharm are LOCAL only! You must push them:**

#### Option 1: Push with commits
1. Press **Ctrl+Shift+K** (Push)
2. In push dialog, check ✅ **"Push Tags"**
3. Select:
   - "All" - pushes all local tags
   - "Current branch" - pushes tags on current branch
4. Click **Push**

#### Option 2: Push tags separately
1. VCS → Git → Push Tags...
2. Select tags to push
3. Click **Push Tags**

#### Option 3: Via Terminal in PyCharm
```bash
# Push specific tag
git push origin v2.0.0

# Push all tags
git push origin --tags
```

### Verifying Tags Are on GitHub

After pushing, verify tags appear on GitHub:

1. **In PyCharm**:
   - Git log should show tag with remote indicator
   - VCS → Git → Branches → Remote tags

2. **On GitHub**:
   - Go to your repository
   - Click the branch dropdown
   - Click "Tags" tab
   - Your tags should be listed

3. **Via command line**:
   ```bash
   # List local tags
   git tag -l
   
   # List remote tags
   git ls-remote --tags origin
   ```

## Creating GitHub Releases

### Step 1: Ensure Tag is on GitHub

**Before creating a release, verify your tag is pushed!**

```bash
# Check if tag exists on GitHub
git ls-remote --tags origin | grep v2.0.0
```

### Step 2: Create Release on GitHub

1. **Navigate to Releases**
   - Go to your repository on GitHub
   - Click "Releases" (right side)
   - Click "Draft a new release"

2. **Configure Release**
   - **Choose a tag**: Select from dropdown (only shows pushed tags!)
   - **Release title**: "v2.0.0 - Enhanced API Resilience"
   - **Description**: Add comprehensive release notes
   - **Pre-release**: Check if beta/RC
   - **Latest release**: Check for stable releases

3. **Generate Release Notes**
   - Click "Generate release notes" button
   - Review auto-generated content
   - Edit and enhance as needed

4. **Save or Publish**
   - **Save draft**: Review later
   - **Publish release**: Make public immediately

### Step 3: Release Notes Template

```markdown
## 🎉 Highlights
Brief overview of major changes

## ✨ Features
- New feature 1
- New feature 2

## 🐛 Bug Fixes
- Fixed issue 1
- Fixed issue 2

## 💔 Breaking Changes
- List any breaking changes

## 📦 Installation
```bash
pip install package==2.0.0
```

## 📚 Documentation
- [Migration Guide](link)
- [API Docs](link)

## 🙏 Contributors
- @username1
- @username2

**Full Changelog**: [v1.0.0...v2.0.0](link)
```

## Troubleshooting

### Tags Not Showing in GitHub Release Dropdown

**Problem**: Created tag in PyCharm but can't select it when creating release

**Solution**: Tag wasn't pushed to GitHub

```bash
# Check if tag exists locally
git tag -l v2.0.0

# Check if tag exists on GitHub
git ls-remote --tags origin | grep v2.0.0

# If local but not remote, push it
git push origin v2.0.0
```

### PyCharm Not Showing Remote Tags

**Solution**: Fetch from remote

1. VCS → Git → Fetch
2. Or in Terminal: `git fetch --tags`

### Deleted Tag Locally but Still on GitHub

```bash
# Delete local tag
git tag -d v2.0.0

# Delete remote tag
git push origin --delete v2.0.0
```

### Wrong Commit Tagged

```bash
# Delete old tag
git tag -d v2.0.0
git push origin --delete v2.0.0

# Create new tag on correct commit
git tag -a v2.0.0 <commit-hash> -m "Message"
git push origin v2.0.0
```

## Internal vs Public Versioning Strategy

### Recommended Approach

#### Internal Tags (Development Team)
Use descriptive tags for development milestones:
```bash
# Internal development tags
dev-2025-01-15-api-complete
test-ready-2025-01-16
qa-approved-2025-01-17
staging-deployed-2025-01-18
```

#### Public Releases (GitHub Releases)
Use semantic versioning for public releases:
```bash
# Public release tags
v1.0.0
v2.0.0
v2.1.0
```

### Implementation Strategy

1. **During Development**:
   ```bash
   # Create internal tag
   git tag -a dev-api-complete -m "API implementation complete"
   git push origin dev-api-complete
   ```

2. **For QA/Testing**:
   ```bash
   # Create test tag
   git tag -a test-v2.0.0-rc1 -m "Release candidate for testing"
   git push origin test-v2.0.0-rc1
   ```

3. **For Production Release**:
   ```bash
   # Create official version tag
   git tag -a v2.0.0 -m "Version 2.0.0 - Production release"
   git push origin v2.0.0
   # Then create GitHub Release
   ```

### Benefits of This Approach

- **Internal tags**: Track development progress
- **Public releases**: Clean version history for users
- **Flexibility**: Can have many internal tags between releases
- **Clarity**: Users only see stable releases

## Complete Workflow Example

### Scenario: Releasing v2.0.0

```bash
# 1. Finish development on feature branch
git checkout feature/v2-enhancements
git commit -m "Final v2 changes"

# 2. Create internal tag for QA
git tag -a qa-v2-ready -m "Ready for QA testing"
git push origin qa-v2-ready

# 3. After QA approval, merge to main
git checkout main
git merge feature/v2-enhancements

# 4. Create release tag
git tag -a v2.0.0 -m "Version 2.0.0 - Enhanced API resilience"

# 5. Push everything to GitHub
git push origin main
git push origin v2.0.0

# 6. Create GitHub Release
# - Go to GitHub.com
# - Create new release
# - Select v2.0.0 tag
# - Add release notes
# - Publish
```

## Quick Reference

### Essential Commands

```bash
# Create annotated tag
git tag -a v2.0.0 -m "Version 2.0.0"

# Push specific tag
git push origin v2.0.0

# Push all tags
git push --tags

# List local tags
git tag -l

# List remote tags
git ls-remote --tags origin

# Delete local tag
git tag -d v2.0.0

# Delete remote tag
git push origin --delete v2.0.0

# Checkout specific tag
git checkout v2.0.0

# See tag details
git show v2.0.0
```

### PyCharm Shortcuts

- **Alt+9**: Open Git window
- **Ctrl+Shift+K**: Push (remember to check "Push Tags")
- **Ctrl+K**: Commit
- **Ctrl+T**: Update project (fetch)

## Best Practices Summary

1. **Always use annotated tags** for releases (`-a` flag)
2. **Push tags explicitly** after creating in PyCharm
3. **Verify tags on GitHub** before creating releases
4. **Use semantic versioning** for public releases
5. **Keep internal tags** separate from version tags
6. **Write comprehensive release notes**
7. **Test locally** before tagging
8. **Tag after merging** to main, not before
9. **Don't reuse tag names** (delete first if needed)
10. **Document breaking changes** clearly

## Additional Resources

- [Semantic Versioning Specification](https://semver.org/)
- [GitHub Releases Documentation](https://docs.github.com/en/repositories/releasing-projects-on-github)
- [Git Tagging Best Practices](https://git-scm.com/book/en/v2/Git-Basics-Tagging)
- [PyCharm Git Integration](https://www.jetbrains.com/help/pycharm/using-git-integration.html)