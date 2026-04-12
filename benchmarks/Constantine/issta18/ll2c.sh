#!/usr/bin/env bash

for dir in "./*"
do
    for file in $dir/*
    do
        name=${file%.*}
        echo $name
        llvm-cbe -march=c -o $name".c" $file
    done
done
