import os

def delete_wav_files(folder_path):
    """
    删除指定目录中的所有 '.wav' 文件。
    :param folder_path: 目标文件夹的路径
    """
    if not os.path.isdir(folder_path):
        print(f"错误：{folder_path} 不是一个目录")
        return

    for file in os.listdir(folder_path):
        if file.lower().endswith(".wav"):
            file_path = os.path.join(folder_path, file)
            os.remove(file_path)

# 示例用法：
if __name__ == "__main__":
    current_directory = os.getcwd()  # 获取当前目录
    delete_wav_files(current_directory)
