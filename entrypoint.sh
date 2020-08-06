#!/bin/sh -l

echo "Hello $1"
time=$(date)
echo "$GITHUB_EVENT_NAME"
echo "::set-output name=time::$time"
