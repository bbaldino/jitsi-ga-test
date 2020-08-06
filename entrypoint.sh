#!/bin/sh -l

echo "Hello $1"
time=$(date)
echo "$GITHUB_EVENT_NAME"
echo "$GITHUB_EVENT_PATH"
cat $GITHUB_EVENT_PATH
echo "::set-output name=time::$time"
