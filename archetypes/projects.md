---
title: "{{ replace .Name "-" " " | title }}"
date: {{ .Date }}
draft: true
categories: ["Projects"]
tags: []
---

# {{ replace .Name "-" " " | title }}

## Overview
Describe your project goals, concept, and inspiration.

## Progress
Document steps, build stages, and painting progress.

## Paint Recipes / Techniques
- Color schemes
- Techniques used
- Notes for future reference

## Photos
![Project Image](/images/{{ .Name }}/example.png)