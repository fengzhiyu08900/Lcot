#!/bin/bash

# 定义 book 文件夹的路径
BOOK_DIR="./books"
# 定义 scene_extractor.py 脚本的路径
EXTRACTOR_SCRIPT="scene_extrator_EN.py"

# 检查 book 文件夹是否存在
if [ ! -d "$BOOK_DIR" ]; then
    echo "错误：'book' 文件夹不存在于当前路径。"
    exit 1
fi

# 检查 scene_extractor_EN.py 脚本是否存在
if [ ! -f "$EXTRACTOR_SCRIPT" ]; then
    echo "错误：'scene_extractor_EN.py' 脚本不存在。"
    exit 1
fi

echo "开始处理 'book' 文件夹下的所有小说..."

# 遍历 book 文件夹下的所有子文件夹
for novel_folder in "$BOOK_DIR"/*/; do
    # 提取文件夹名称作为小说书名
    # basename "$novel_folder" 会得到类似 "小说 A" 的名称
    novel_title=$(basename "$novel_folder")

    echo "---"
    echo "正在处理小说：'$novel_title'"
    # 关键修改：使用双引号包裹 "$novel_title"
    echo "运行命令：python \"$EXTRACTOR_SCRIPT\" \"$novel_title\""

    # 运行 python 脚本，并将小说书名作为参数传递
    # 关键修改：使用双引号包裹 "$novel_title"
    python $EXTRACTOR_SCRIPT "$novel_title"

    if [ $? -eq 0 ]; then
        echo "小说 '$novel_title' 处理成功。"
    else
        echo "处理小说 '$novel_title' 失败。请检查 'scene_extractor.py' 的输出。"
    fi
done

echo "---"
echo "所有小说处理完成。"