# Uploads Directory

This directory stores the original PowerPoint (.pptx) files uploaded by users. I already delete them auto btw when deleting a class, need to delete the pdf aswell tho

## Structure

Files are named with a pattern: `class_{class_id}_{original_filename}.pptx`

Example:
```
uploads/
  ├── class_1_Introduction_to_Python.pptx
  ├── class_2_Data_Structures.pptx
  └── class_5_Machine_Learning_Basics.pptx
```

## Backend Usage

The file paths are stored in the database (`presentations.original_pptx_path`) and are used to:
1. Extract text content from slides
2. Convert slides to images for display
3. Generate AI responses based on slide content
