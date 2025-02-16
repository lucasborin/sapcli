# git enabled Change Transport System (gCTS)

sapcli's implementation forces use of packages as git repositories.

1. [repolist](#repolist)
2. [clone](#clone)
3. [checkout](#checkout)
4. [log](#log)
5. [pull](#pull)
6. [commit](#commit)
7. [delete](#delete)
8. [config](#config)
9. [user get-credentials](#user-get-credentials)
10. [user set-credentials](#user-set-credentials)
11. [user delete-credentials](#user-delete-credentials)
12. [repo set-url](#repo-set-url)
13. [repo property get](#repo-property-get)
14. [repo property set](#repo-property-set)
15. [repo branch create](#repo-branch-create)
16. [repo branch delete](#repo-branch-delete)
17. [repo branch list](#repo-branch-list)
18. [repo activities](#repo-activities)
19. [system config get](#system-config-get)
20. [system config list](#system-config-list)
21. [system config set](#system-config-set)
22. [system config unset](#system-config-unset)

## repolist

Get list of ABAP packages versioned as gCTS repositories

```bash
sapcli gcts repolist
```

## clone

Creates and pulls a new repository. If the argument package is
not given, the name is taken from repository name.

```bash
sapcli gcts clone [--vsid VSID] [--starting-folder FOLDER] [--role ROLE] [--type TYPE] [--vcs-token TOKEN] URL [package]
```

**Parameters**:
- `--wait-for-ready SECONDS`: Wait for the repository to be in status `READY` for the given number of seconds 
- `--heartbeat SECONDS`: Console heart beat printing dots
- `--no-fail-exists`: If repository exists do not fail but try to clone
- `--vsid VSID`: Virtual System ID of the repository; default is **6IT**
- `--starting-folder FOLDER`: The directory inside the repository where to store ABAP files; default is **src/**.
- `--role ROLE`: Either SOURCE (Development) or TARGET (Provided); default is **SOURCE**
- `--type TYPE`: Either GIT or GITHUB; default is **GITHUB**
- `--vcs-token TOKEN`: Authentication token
- `URL`: Repository HTTP URL
- `package`: gCTS repository name; if no provided, deduced from URL

## checkout

Checkout branch

```bash
sapcli gcts checkout [--format HUMAN|JSON] PACKAGE BRANCH
```

**Parameters:**:
- `--format`: Output format. The JSON format is particularly useful for automations because it contains Transport Request number.
- `PACKAGE`: Repository name or URL
- `BRANCH`: Name of the branch to checkout

## log

Print out repository history log

```bash
sapcli gcts log PACKAGE
```

**Parameters:**:
- `PACKAGE`: Repository name or URL

## pull

Pulls the repository on the system

```bash
sapcli gcts pull PACKAGE
```

**Parameters:**:
- `PACKAGE`: Repository name or URL

## commit

Commits & pushes a transport to the correspoding repository

```bash
sapcli gcts commit PACKAGE CORRNR [-m|--message MESSAGE] [--description DESCRIPTION]
```

**Parameters:**:
- `PACKAGE`: Repository name or URL
- `CORRNR`: Transport number (e.g. from *sapcli cts list transport*)
- `--message MESSAGE`: Short commit messsage
- `--description DESCRIPTION`: Commit message body

## delete

Removes the repository not the package

```bash
sapcli gcts delete PACKAGE
```

**Parameters:**:
- `PACKAGE`: Repository name or URL

## config

Configure the given repository. To set the configuration property, specify `NAME` and `VALUE`.
To unset the property, run the command with `--unset` option and specify `NAME`. To list all
configuration properties, run the command with `--list` option.

```bash
sapcli gcts config [-l|--list] [--unset] PACKAGE [NAME] [VALUE]
```

**Parameters:**:
- `PACKAGE`: Repository name or URL
- `NAME`: Name of configuration property
- `VALUE`: Value that will be assigned to the property
- `--unset`: Unset given configuration property
- `--list`: Lists all configuration options for the specified repository

## user get-credentials

Get credentials of the logged in user

```bash
sapcli gcts user get-credentials [-f|--format] {HUMAN|JSON}
```

**Parameters:**
- `--format`: The format of the command's output

## user set-credentials

Set credentials of the logged in user

```bash
sapcli gcts user set-credentials --api-url [URL] --token [TOKEN]
```

**Parameters:**:
- `--api-url [URL]`: API URL
- `--token [TOKEN]`: The secret token

## user delete-credentials

Delete credentials of the logged in user

```bash
sapcli gcts user delete-credentials --api-url [URL]
```

**Parameters:**
- `--api-url [URL]`: API URL to delete

## repo set-url

Change URL of the given repository identified by package name (sapcli tries to
push users to map packages to repositories).

```bash
sapcli gcts repo set-url PACKAGE URL
```

**Parameters:**:
- `PACKAGE`: The repository name
- `URL`: The new url

## repo property get

Get properties of the given repository.

```bash
sapcli gcts repo property get PACKAGE
```

**Parameters:**:
- `PACKAGE`: The repository name

## repo property set

Set the specified property of the given repository.

```bash
sapcli gcts repo property set PACKAGE PROPERTY_NAME VALUE
```

**Parameters:**:
- `PACKAGE`: The repository name
- `PROPERTY_NAME`: The name of the property that is to be changed
- `VALUE`: New value for the specified property

## repo branch create

Create and switch to the new branch. By default, the command creates `local` and `remote` branch.
This behavior can be overriden by `--local-only` argument.

```bash
sapcli gcts repo branch create PACKAGE NAME [--symbolic] [--peeled] [--local-only] [-f|--format] {HUMAN|JSON}
```

**Parameters**:
- `PACKAGE`: The repository name
- `NAME`: The name of a new branch
- `--symbolic`: The new branch will be symbolic
- `--peeled`: The new branch will be peeled
- `--local-only`: Create only `local` branch.
- `--format`: The format of the command's output

## repo branch delete

Delete the branch. Note, the branch cannot be active.

```bash
sapcli gcts repo branch delete PACKAGE NAME [-f|--format] {HUMAN|JSON}
```

**Parameters**:
- `PACKAGE`: The repository name
- `NAME`: The name of a new branch
- `--format`: The format of the command's output

## repo branch list

List branches of a repository. The active branch is marked by `*` only in `HUMAN` format.

```bash
sapcli gcts repo branch list PACKAGE [-a|--all] [-r|--remote] [-f|--format] {HUMAN|JSON}
```

**Parameters**:
- `PACKAGE`: The repository name
- `--all`: List all branches
- `--remote`: List `remote` branches only
- `--format`: The format of the command's output

## repo activities

List activities (history) of a repository. 

Note, the `operation` parameter corresponds to the type of activity.

```bash
sapcli gcts repo activities PACKAGE [--limit LIMIT] [--offset OFFSET] [--fromcommit FROMCOMMIT] [--tocommit TOCOMMIT] [--operation] {COMMIT,PULL,CLONE,BRANCH_SW} [--noheadings] [--columns] [-f|--format] {HUMAN|JSON}
```

**Parameters**:
- `PACKAGE`: The repository name
- `--limit LIMIT`: The maximum number of activities to return
- `--offset OFFSET`: The offset of the first activity to return
- `--fromcommit FROMCOMMIT`: The From Commit hash of activities to return
- `--tocommit TOCOMMIT`: The To Commit hash of activities to return
- `--operation {COMMIT,PULL,CLONE,BRANCH_SW}`: The type of activities to return. Possible values follow domain of `SCTS_ABAP_VCS_COMMIT_TYPE`.
- `--noheadings`: Do not display a header line
- `--columns`: Specify the columns to display

## system config get

Get the specific system configuration property.

```bash
sapcli gcts system config get KEY [-f|--format] {HUMAN|JSON}
```

**Parameters**:
- `KEY`: The identifier of configuration property
- `--format`: The format of the command's output


## system config list

List the system configuration.

```bash
sapcli gcts system config list [-f|--format] {HUMAN|JSON}
```

**Parameters**:
- `--format`: The format of the command's output

## system config set

Create or update the system configuration property.

```bash
sapcli gcts system config set KEY VALUE [-f|--format] {HUMAN|JSON}
```

**Parameters**:
- `KEY`: The identifier of configuration property
- `VALUE`: The value that will be assigned to the property
- `--format`: The format of the command's output


## system config unset

Delete the system configuration property.

```bash
sapcli gcts system config unset KEY [-f|--format] {HUMAN|JSON}
```

**Parameters**:
- `KEY`: The identifier of configuration property
- `--format`: The format of the command's output


# Deprecated
- command [repo set-url](#repo-set-url) is replaced by [repo property set](#TODO) with property
  set to `url`
