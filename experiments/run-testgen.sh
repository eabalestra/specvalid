#!/bin/bash

# Verify that the required environment variables have been set
[[ -z "$SPECVALID" ]] && {
  echo "> The environment variable SPECVALID is empty"
  exit 1
}
[[ -z "$GASSERTDIR" ]] && {
  echo "> The environment variable GASSERTDIR is empty"
  exit 1
}

# Read arguments
gassert_subject=$1
fqname=$2
method_name=$3

gassert_dir=$GASSERTDIR
subject_sources=$gassert_dir/subjects/$gassert_subject
class_package=$(echo "$fqname" | sed 's/\.[^.]*$//')