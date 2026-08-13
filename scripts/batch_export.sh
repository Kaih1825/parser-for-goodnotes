#!/bin/bash
# 自動匯出 GoodNotes 筆記為 SVG
files=(
    "Ch3P1.goodnotes"
    "shape.goodnotes"
    "Teat.goodnotes"
    "pencil.goodnotes"
    "tri.goodnotes"
    "ooo.goodnotes"
    "國際情勢.goodnotes"
    "aaa.goodnotes"
    "aaa2.goodnotes"
    "Move.goodnotes"
    "p5.goodnotes"
    "tri2.goodnotes"
    "Small.goodnotes"
    "sticker.goodnotes"
    "muti.goodnotes"
    "abcd.goodnotes"
    "shape2.goodnotes"
    "blue.goodnotes"
    "shapeTest.goodnotes"
    "shape3.goodnotes"
    "pageTest.goodnotes"
    "pageatset2.goodnotes"
    "order_after.goodnotes"
    "order_before.goodnotes"
    "imgTest.goodnotes"
    "imgTest2.goodnotes"
    "text.goodnotes"
    "bacTest.goodnotes"
    "NewGN6.goodnotes"
    "Page1.goodnotes"
)

mkdir -p output_svgs

for file in "${files[@]}"; do
    target=""
    if [ -f "../samples/$file" ]; then
        target="../samples/$file"
    elif [ -f "../$file" ]; then
        target="../$file"
    fi

    if [ -n "$target" ]; then
        echo "正在匯出: $target -> output_svgs/"
        uv run gn-export-svg "$target" -o "output_svgs" -s open
        # uv run gn-export-svg "$target" -o "output_svgs" -b open -s open
    else
        echo "找不到檔案: $file，跳過。"
    fi
done

echo "全部匯出完成！匯出結果已儲存至 output_svgs/ 目錄。"
