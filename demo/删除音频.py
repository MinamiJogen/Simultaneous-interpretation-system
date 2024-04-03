import os

def delete_wav_files():
    current_directory = os.getcwd()  # 获取当前目录
    """
    删除指定目录中的所有 '.wav' 文件。
    :param folder_path: 目标文件夹的路径
    """
    if not os.path.isdir(current_directory):
        print(f"错误：{current_directory} 不是一个目录")
        return

    for file in os.listdir(current_directory):
        if file.lower().endswith(".wav"):
            file_path = os.path.join(current_directory, file)
            os.remove(file_path)

# 示例用法：
if __name__ == "__main__":
    
    delete_wav_files()
