#!/usr/bin/env python3
"""
Clean ChatGPT Export

功能：
1. 只保留 OpenClaw 相关对话（3个）
2. 删除其他所有无关对话
3. 保留音频文件
4. 保留粘贴的文本/markdown 文件
5. 生成清理后的文件
"""

import json
import shutil
import sys
from pathlib import Path

# 要保留的对话 ID（OpenClaw 相关）
OPENCLAW_CONVERSATION_IDS = {
    "69e4ec6f-cdf4-83ea-9f02-46ab46951754",  # Branch 与 OpenClaw：分支计划备份 (5483节点)
    "69dfc820-3a28-832a-96ea-d212aa415fca",  # OpenClaw改造计划备份 (492节点)
    "69ef0762-87bc-83ea-a6d4-cf8d3424fe7d",  # OpenClaw 系统能否写入 (109节点)
}


def clean_conversations(input_file: str, output_file: str):
    """清理对话文件，只保留 OpenClaw 相关对话"""

    print(f"读取原始文件: {input_file}")
    with open(input_file, 'r', encoding='utf-8') as f:
        data = json.load(f)

    print(f"原始对话数量: {len(data)}")

    # 过滤只保留 OpenClaw 相关
    filtered = [conv for conv in data if conv.get('id') in OPENCLAW_CONVERSATION_IDS]

    print(f"保留对话数量: {len(filtered)}")

    # 显示保留的对话
    for conv in filtered:
        mapping = conv.get('mapping', {})
        print(f"  - {conv.get('title', '无标题')} ({len(mapping)} 节点)")

    # 写入新文件
    print(f"\n写入清理后文件: {output_file}")
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(filtered, f, ensure_ascii=False, indent=2)

    return filtered


def copy_attachments(
    input_dir: str,
    output_dir: str,
    conversation_ids: set
):
    """
    复制附件文件

    ChatGPT 导出的附件命名规则：
    - 音频: file_XXXXX-XXX.wav (在 audio/ 子目录)
    - 粘贴的文本: file_XXXXX-*粘贴的文本*.txt
    - 粘贴的Markdown: file_XXXXX-*粘贴的 markdown*.md

    注意：附件可能与特定对话关联，但我们无法直接从文件名判断关联性
    所以我们保留所有附件，或者让用户指定
    """

    input_path = Path(input_dir)
    output_path = Path(output_dir)

    # 创建输出目录
    audio_dir = output_path / "audio"
    audio_dir.mkdir(parents=True, exist_ok=True)

    # 复制音频文件（保留目录结构）
    audio_source = input_path / "69ec2a1d-fe14-83ea-b646-c29a75328aaf" / "audio"
    if audio_source.exists():
        print(f"\n复制音频文件...")
        count = 0
        for wav_file in audio_source.glob("*.wav"):
            dest = audio_dir / wav_file.name
            shutil.copy2(wav_file, dest)
            count += 1
        print(f"  复制了 {count} 个音频文件")

    # 复制粘贴的文本文件（这些是对话中用户粘贴的内容）
    print(f"\n复制粘贴的文本/markdown 文件...")
    count = 0
    for txt_file in input_path.glob("*粘贴的文本*.txt"):
        shutil.copy2(txt_file, output_path / txt_file.name)
        count += 1
    for md_file in input_path.glob("*粘贴的 markdown*.md"):
        shutil.copy2(md_file, output_path / md_file.name)
        count += 1
    print(f"  复制了 {count} 个文本/markdown 文件")

    return output_path


def generate_summary(kept_conversations: list, output_dir: str):
    """生成清理报告"""

    report = []
    report.append("# ChatGPT 导出清理报告")
    report.append("")
    report.append("## 保留的对话\n")

    total_nodes = 0
    for conv in kept_conversations:
        mapping = conv.get('mapping', {})
        total_nodes += len(mapping)

        # 统计消息数
        user_msgs = 0
        assistant_msgs = 0
        for node in mapping.values():
            msg = node.get('message')
            if msg:
                role = msg.get('author', {}).get('role')
                if role == 'user':
                    user_msgs += 1
                elif role == 'assistant':
                    assistant_msgs += 1

        report.append(f"### {conv.get('title', '无标题')}")
        report.append(f"- ID: `{conv.get('id')}`")
        report.append(f"- 总节点: {len(mapping)}")
        report.append(f"- 用户消息: {user_msgs}")
        report.append(f"- AI 回复: {assistant_msgs}")
        report.append("")

    report.append(f"## 统计")
    report.append(f"- 对话总数: {len(kept_conversations)}")
    report.append(f"- 总节点数: {total_nodes}")
    report.append("")
    report.append("## 清理说明")
    report.append("- 已删除所有非 OpenClaw 相关对话")
    report.append("- 保留了音频文件（语音转文字的原始音频）")
    report.append("- 保留了粘贴的文本/markdown 文件（对话中上传的内容）")

    report_path = Path(output_dir) / "CLEANUP_REPORT.md"
    report_path.write_text("\n".join(report), encoding='utf-8')
    print(f"\n清理报告已生成: {report_path}")

    return report_path


def main():
    import argparse

    parser = argparse.ArgumentParser(description="清理 ChatGPT 导出文件")
    parser.add_argument(
        '--input',
        '-i',
        required=True,
        help='原始 conversations.json 路径'
    )
    parser.add_argument(
        '--input-dir',
        '-d',
        required=True,
        help='解压后的导出目录'
    )
    parser.add_argument(
        '--output-dir',
        '-o',
        default='./cleaned_export',
        help='清理后的输出目录'
    )

    args = parser.parse_args()

    output_path = Path(args.output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    print("=" * 60)
    print("  ChatGPT 导出清理工具")
    print("=" * 60)
    print()

    # 1. 清理并保存 conversations.json
    cleaned_file = output_path / "conversations.json"
    kept = clean_conversations(args.input, str(cleaned_file))

    # 2. 复制附件
    copy_attachments(args.input_dir, str(output_path), OPENCLAW_CONVERSATION_IDS)

    # 3. 生成报告
    generate_summary(kept, str(output_path))

    print()
    print("=" * 60)
    print(f"  清理完成！输出目录: {output_path}")
    print("=" * 60)
    print()
    print("输出文件:")
    print(f"  - conversations.json (清理后的对话)")
    print(f"  - audio/ (音频文件)")
    print(f"  - *粘贴的文本*.txt (文本附件)")
    print(f"  - CLEANUP_REPORT.md (清理报告)")


if __name__ == "__main__":
    main()
