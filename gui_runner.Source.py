import tkinter as tk
from tkinter import filedialog, messagebox
import os
import subprocess
import sys
import platform
import shutil
import random
import time
import threading
from tkinter.font import Font
from pathlib import Path
import io

class DashboardApp:
    def __init__(self, master):
        self.master = master
        self.process = None
        self.settings = {"labels_before": "", "labels_done": ""}
        self.master.title("Mosaic tool Dashboard")
        self.master.geometry("1000x700")
        self.master.configure(bg="#1e1e2e")
        self.master.protocol("WM_DELETE_WINDOW", self.on_closing)
        self.default_font = Font(family="Quicksand", size=11)
        self.master.option_add("*Font", self.default_font)

        self.sidebar_width = 200
        self.build_layout()
        self.show_home()

        self.TOTAL_STEPS = 5
        self.current_step = 0
        self.log_text = ""
        self.animation_running = False
        self.animation_chars = [".....", "///"]
        self.animation_index = 0

        self.original_stdout = sys.stdout
        self.output_buffer = io.StringIO()

        self.label_studio_button = None

        # 初期化時に conda_env のチェックを削除
        # ボタンの初期状態は show_label_create で明示的に有効化
        self.conda_env_exists = False

    def disable_button(self):
        if self.label_studio_button:
            self.label_studio_button.config(state="disabled", bg="#6b6bb5")

    def enable_button(self):
        if self.label_studio_button:
            self.label_studio_button.config(state="normal", bg="#8e8ee5")

    def start_animation(self):
        if not self.animation_running:
            self.animation_running = True
            self.update_animation()

    def stop_animation(self):
        self.animation_running = False
        self.animation_index = 0
        self.update_log(self.log_text.rstrip(".....").rstrip("///"))

    def update_animation(self):
        if not self.animation_running:
            return
        base_text = self.log_text.rstrip(".....").rstrip("///")
        self.animation_index = (self.animation_index + 1) % len(self.animation_chars)
        new_text = base_text + self.animation_chars[self.animation_index]
        self.update_log(new_text)
        self.master.after(500, self.update_animation)

    def update_log(self, message):
        self.log_text = message
        if hasattr(self, 'log_label'):
            self.log_label.config(text=self.log_text)

    def launch_label_studio(self):
        # 変更点: プロセス重複チェックを削除し、複数インスタンスの起動を許可
        # 変更点: スクリプトまたはEXEと同じディレクトリを取得
        if getattr(sys, 'frozen', False):
            # PyInstallerでEXE化されている場合、EXEのディレクトリを使用
            script_dir = os.path.dirname(os.path.abspath(sys.executable))
        else:
            # 通常のPython実行時、スクリプトのディレクトリを使用
            script_dir = os.path.dirname(os.path.abspath(__file__))

        venv_dir = os.path.join(script_dir, "conda_env")
        label_studio_exe = os.path.join(venv_dir, "Scripts" if os.name == "nt" else "bin", "label-studio" + (".exe" if os.name == "nt" else ""))
        self.conda_env_exists = os.path.exists(venv_dir) and os.path.isfile(label_studio_exe)

        # conda_env が存在しない場合、ボタンを無効化
        if not self.conda_env_exists:
            print("conda_env が見つかりません。仮想環境構築中はボタンを無効化します。")
            self.disable_button()

        self.update_log("Label Studio を起動しています")
        self.start_animation()

        sys.stdout = self.output_buffer
        # 仮想環境構築または起動処理を別スレッドで開始
        threading.Thread(target=self._launch_label_studio_thread, args=(script_dir,), daemon=True).start()

    def _launch_label_studio_thread(self, script_dir):
        try:
            venv_dir = os.path.join(script_dir, "conda_env")
            label_studio_exe = os.path.join(venv_dir, "Scripts" if os.name == "nt" else "bin", "label-studio" + (".exe" if os.name == "nt" else ""))

            if self.conda_env_exists:
                print("conda_env が見つかりました。label-studio を直接起動します。")
                self.output_buffer.seek(0)
                output = self.output_buffer.getvalue()
                self.master.after(0, lambda: self.update_log(output.rstrip()))
                self.output_buffer.truncate(0)
                self.output_buffer.seek(0)
                self._start_label_studio(label_studio_exe, script_dir)
                self.master.after(0, self.enable_button)
                return

            print("conda_env が見つかりません。Conda 環境を構築します。")
            self.output_buffer.seek(0)
            output = self.output_buffer.getvalue()
            self.master.after(0, lambda: self.update_log(output.rstrip()))
            self.output_buffer.truncate(0)
            self.output_buffer.seek(0)

            env_name = "conda_env"
            conda_bin = "conda"

            try:
                result = subprocess.run(
                    [conda_bin, "env", "list"],
                    capture_output=True,
                    text=True,
                    check=True,
                    encoding="utf-8"
                )
                env_list = result.stdout
                env_exists = any(f"{env_name} " in line or f"/{env_name}" in line for line in env_list.splitlines())
            except subprocess.CalledProcessError as e:
                self.master.after(0, lambda: messagebox.showerror("エラー", f"Conda環境の確認に失敗しました:\n{e}\nCondaが正しくインストールされているか確認してください。"))
                self.stop_animation()
                sys.stdout = self.original_stdout
                self.master.after(0, self.disable_button)
                return

            python_exe = os.path.join(venv_dir, "python.exe" if os.name == "nt" else "bin/python")

            if not env_exists or not os.path.isfile(python_exe):
                try:
                    print(f"Python 3.10.9 のConda環境を作成しています: {venv_dir}")
                    self.output_buffer.seek(0)
                    output = self.output_buffer.getvalue()
                    self.master.after(0, lambda: self.update_log(output.rstrip()))
                    self.output_buffer.truncate(0)
                    self.output_buffer.seek(0)

                    if os.path.exists(venv_dir):
                        shutil.rmtree(venv_dir)
                    subprocess.run(
                        [conda_bin, "create", "-p", venv_dir, "python=3.10.9", "-c", "conda-forge", "-y"],
                        check=True,
                        capture_output=True,
                        text=True,
                        encoding="utf-8"
                    )
                    print("Conda環境の作成が完了しました。")
                    self.output_buffer.seek(0)
                    output = self.output_buffer.getvalue()
                    self.master.after(0, lambda: self.update_log(output.rstrip()))
                    self.output_buffer.truncate(0)
                    self.output_buffer.seek(0)
                except subprocess.CalledProcessError as e:
                    error_msg = f"Conda環境の作成に失敗しました:\n{e}\n"
                    if e.stdout:
                        error_msg += f"標準出力: {e.stdout}\n"
                    if e.stderr:
                        error_msg += f"エラー出力: {e.stderr}\n"
                    self.master.after(0, lambda: messagebox.showerror("エラー", error_msg))
                    self.stop_animation()
                    sys.stdout = self.original_stdout
                    self.master.after(0, self.disable_button)
                    return

            try:
                print("pipをアップグレードしています...")
                self.output_buffer.seek(0)
                output = self.output_buffer.getvalue()
                self.master.after(0, lambda: self.update_log(output.rstrip()))
                self.output_buffer.truncate(0)
                self.output_buffer.seek(0)

                result = subprocess.run(
                    [python_exe, "-m", "pip", "install", "--upgrade", "pip"],
                    check=True,
                    capture_output=True,
                    text=True,
                    encoding="utf-8"
                )
                print("pipのアップグレードが完了しました。")
                self.output_buffer.seek(0)
                output = self.output_buffer.getvalue()
                self.master.after(0, lambda: self.update_log(output.rstrip()))
                self.output_buffer.truncate(0)
                self.output_buffer.seek(0)
            except subprocess.CalledProcessError as e:
                error_msg = f"pipのアップグレードに失敗しました:\n{e}\n"
                if e.stdout:
                    error_msg += f"標準出力: {e.stdout}\n"
                if e.stderr:
                    error_msg += f"エラー出力: {e.stderr}"
                self.master.after(0, lambda: messagebox.showerror("エラー", error_msg))
                self.stop_animation()
                sys.stdout = self.original_stdout
                self.master.after(0, self.disable_button)
                return

            try:
                print("依存パッケージをCondaでインストールしています...")
                self.output_buffer.seek(0)
                output = self.output_buffer.getvalue()
                self.master.after(0, lambda: self.update_log(output.rstrip()))
                self.output_buffer.truncate(0)
                self.output_buffer.seek(0)

                dependencies = ["numpy", "pandas", "psycopg2", "pyyaml"]
                subprocess.run(
                    [conda_bin, "install", "-p", venv_dir, "-c", "conda-forge", "-y"] + dependencies,
                    check=True,
                    capture_output=True,
                    text=True,
                    encoding="utf-8"
                )
                print("依存パッケージのインストールが完了しました。")
                self.output_buffer.seek(0)
                output = self.output_buffer.getvalue()
                self.master.after(0, lambda: self.update_log(output.rstrip()))
                self.output_buffer.truncate(0)
                self.output_buffer.seek(0)
            except subprocess.CalledProcessError as e:
                error_msg = f"依存パッケージのインストールに失敗しました:\n{e}\n"
                if e.stdout:
                    error_msg += f"標準出力: {e.stdout}\n"
                if e.stderr:
                    error_msg += f"エラー出力: {e.stderr}\n"
                    error_msg += "Windows環境では Microsoft Visual C++ Build Tools が必要です。以下のリンクからインストールしてください:\n"
                    error_msg += "https://visualstudio.microsoft.com/visual-cpp-build-tools/\n"
                error_msg += "または、Condaで依存パッケージを再インストールしてみてください。"
                self.master.after(0, lambda: messagebox.showerror("エラー", error_msg))
                self.stop_animation()
                sys.stdout = self.original_stdout
                self.master.after(0, self.disable_button)
                return

            if not os.path.isfile(label_studio_exe):
                try:
                    print("label-studioをインストールしています...")
                    self.output_buffer.seek(0)
                    output = self.output_buffer.getvalue()
                    self.master.after(0, lambda: self.update_log(output.rstrip()))
                    self.output_buffer.truncate(0)
                    self.output_buffer.seek(0)

                    result = subprocess.run(
                        [python_exe, "-m", "pip", "install", "label-studio"],
                        check=True,
                        capture_output=True,
                        text=True,
                        encoding="utf-8"
                    )
                    print("label-studio のインストールが完了しました。")
                    self.output_buffer.seek(0)
                    output = self.output_buffer.getvalue()
                    self.master.after(0, lambda: self.update_log(output.rstrip()))
                    self.output_buffer.truncate(0)
                    self.output_buffer.seek(0)
                except subprocess.CalledProcessError as e:
                    error_msg = f"label-studio のインストールに失敗しました:\n{e}\n"
                    if e.stdout:
                        error_msg += f"標準出力: {e.stdout}\n"
                    if e.stderr:
                        error_msg += f"エラー出力: {e.stderr}\n"
                    if os.name == "nt":
                        error_msg += "Windows環境では、Microsoft Visual C++ Build Toolsが必要です。以下のリンクからインストールしてください:\n"
                        error_msg += "https://visualstudio.microsoft.com/visual-cpp-build-tools/\n"
                    error_msg += "または、Condaで依存パッケージを再インストールしてみてください。"
                    self.master.after(0, lambda: messagebox.showerror("エラー", error_msg))
                    self.stop_animation()
                    sys.stdout = self.original_stdout
                    self.master.after(0, self.disable_button)
                    return

            self.conda_env_exists = os.path.exists(venv_dir) and os.path.isfile(label_studio_exe)
            self.master.after(0, self.enable_button)
            self._start_label_studio(label_studio_exe, script_dir)

        except Exception as e:
            self.master.after(0, lambda: messagebox.showerror("エラー", f"予期しないエラーが発生しました:\n{e}"))
            print(f"デバッグ情報: {e}")
            self.stop_animation()
            sys.stdout = self.original_stdout
            self.master.after(0, self.enable_button)

    def _start_label_studio(self, label_studio_exe, script_dir):
        """Label Studio を起動する共通ロジック"""
        try:
            if not os.path.isfile(label_studio_exe):
                self.master.after(0, lambda: messagebox.showerror("エラー", f"label-studio 実行ファイルが見つかりません:\n{label_studio_exe}\nインストールが正しく完了していない可能性があります。"))
                self.stop_animation()
                sys.stdout = self.original_stdout
                self.master.after(0, self.enable_button)
                return

            env = os.environ.copy()
            env["PYTHONUTF8"] = "1"
            env["PYTHONIOENCODING"] = "utf-8"
            env["LC_ALL"] = "C.UTF-8"
            env["LANG"] = "C.UTF-8"

            creationflags = 0
            if os.name == 'nt':
                creationflags = subprocess.CREATE_NO_WINDOW | subprocess.CREATE_NEW_PROCESS_GROUP

            # 変更点: 新しいプロセスを追跡しない（self.process に代入しない）
            process = subprocess.Popen(
                [label_studio_exe, "--port", "8081"],
                cwd=script_dir,
                env=env,
                creationflags=creationflags,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )

            def monitor_process():
                stdout, stderr = process.communicate()
                if process.poll() is not None:
                    if process.returncode != 0:
                        error_output = stderr if stderr else "不明なエラー"
                        print(f"Label Studio 起動失敗 (終了コード {process.returncode}):\n{error_output}")
                        self.master.after(0, lambda: self.update_log(f"Label Studio 起動失敗 (終了コード {process.returncode})"))
                        self.master.after(0, lambda: messagebox.showerror("起動エラー", f"Label Studio の起動に失敗しました (終了コード {process.returncode}):\n{error_output}"))
                    else:
                        print("Label Studio プロセスが終了しました。")
                        self.master.after(0, lambda: self.update_log("Label Studio プロセスが終了しました。"))
                else:
                    self.master.after(0, lambda: self.update_log("Label Studio を起動しました。localhost:8081 をご確認ください。"))
                    self.master.after(0, lambda: messagebox.showinfo("情報", "Label Studio を起動しました。localhost:8081 をご確認ください。"))

                self.stop_animation()
                sys.stdout = self.original_stdout
                self.master.after(0, self.enable_button)

            threading.Thread(target=monitor_process, daemon=True).start()

        except Exception as e:
            self.master.after(0, lambda: messagebox.showerror("エラー", f"Label Studio の起動に失敗しました:\n{e}"))
            print(f"デバッグ情報: {e}")
            self.stop_animation()
            sys.stdout = self.original_stdout
            self.master.after(0, self.enable_button)

    def print_progress_inline(self):
        filled = int(25 * self.current_step / self.TOTAL_STEPS)
        bar = "█" * filled + "→" + "-" * (25 - filled)
        percent = int(self.current_step / self.TOTAL_STEPS * 100)
        log_message = f"[{bar}] {percent}%"
        self.master.after(0, self.update_log, log_message)

    def generate_yaml(self, base_dir):
        try:
            import yaml
        except ImportError as e:
            messagebox.showerror("エラー", f"yaml モジュールが見つかりません:\n{e}\n仮想環境を再構築してください。")
            return

        classes_path = os.path.join(base_dir, "classes.txt")

        if not os.path.isfile(classes_path):
            self.master.after(0, self.update_log, "classes.txt が存在しないため、推測します。")
            label_dir = os.path.join(base_dir, "train", "labels")
            labels = set()
            if os.path.isdir(label_dir):
                for file in os.listdir(label_dir):
                    if file.endswith(".txt"):
                        file_path = os.path.join(label_dir, file)
                        try:
                            with open(file_path, "r", encoding="utf-8") as f:
                                for line in f:
                                    if line.strip():
                                        cls_id = line.split()[0]
                                        labels.add(cls_id)
                        except Exception as e:
                            self.master.after(0, self.update_log, f"⚠ ファイル {file} の読み込みに失敗しました: {e}")
            if labels:
                labels = sorted(labels, key=lambda x: int(x) if x.isdigit() else x)
                try:
                    with open(classes_path, "w", encoding="utf-8") as f:
                        for label in labels:
                            f.write(f"class_{label}\n")
                except Exception as e:
                    self.master.after(0, self.update_log, f"⚠ classes.txt の書き込みに失敗しました: {e}")
                    return
            else:
                self.master.after(0, self.update_log, "⚠ ラベルが見つかりませんでした。classes.txt を作成できません。")
                return

        classes = []
        try:
            with open(classes_path, "r", encoding="utf-8") as f:
                classes = [line.strip() for line in f if line.strip()]
        except Exception as e:
            self.master.after(0, self.update_log, f"⚠ classes.txt の読み込みに失敗しました: {e}")
            return

        if not classes:
            self.master.after(0, self.update_log, "⚠ classes.txt が空です。")
            return

        data = {
            "path": base_dir.replace("\\", "/"),
            "train": "train/images",
            "val": "val/images",
            "nc": len(classes),
            "names": classes
        }

        output_yaml_path = os.path.join(base_dir, "data.yaml")
        try:
            with open(output_yaml_path, "w", encoding="utf-8") as f:
                yaml.dump(data, f, allow_unicode=True)
        except Exception as e:
            self.master.after(0, self.update_log, f"⚠ data.yaml の書き込みに失敗しました: {e}")
            return

        self.current_step += 1
        self.print_progress_inline()
        self.master.after(0, self.update_log, f"data.yaml output done: {output_yaml_path}")

    def find_folders(self, start_dir):
        images_dir = None
        labels_dir = None
        for root, dirs, files in os.walk(start_dir):
            if "images" in dirs:
                images_dir = os.path.join(root, "images")
            if "labels" in dirs:
                labels_dir = os.path.join(root, "labels")
            if images_dir and labels_dir and (images_dir.startswith(root) and labels_dir.startswith(root)):
                break
        return images_dir, labels_dir

    def split_yolo_dataset_with_clone(self, source_dir, output_base_dir, split_ratio=0.7):
        self.current_step = 0
        self.print_progress_inline()
        self.master.after(100)

        original_name = os.path.basename(source_dir.rstrip("\\/"))
        output_dir = os.path.join(output_base_dir, f"{original_name}_done")
        os.makedirs(output_dir, exist_ok=True)

        try:
            for item in os.listdir(source_dir):
                s = os.path.join(source_dir, item)
                d = os.path.join(output_dir, item)
                if os.path.isdir(s):
                    shutil.copytree(s, d, dirs_exist_ok=True)
                else:
                    shutil.copy2(s, d)
        except Exception as e:
            self.master.after(0, self.update_log, f"❌ ファイルの複製に失敗しました: {e}")
            return

        self.current_step += 1
        self.print_progress_inline()
        self.master.after(0, self.update_log, "複製完了")

        image_dir, label_dir = self.find_folders(output_dir)
        if not image_dir or not label_dir:
            self.master.after(0, self.update_log, "❌ 'images' または 'labels' フォルダが見つかりませんでした。")
            return

        train_image_dir = os.path.join(image_dir, "train")
        val_image_dir = os.path.join(image_dir, "val")
        train_label_dir = os.path.join(label_dir, "train")
        val_label_dir = os.path.join(label_dir, "val")

        valid_exts = (".jpg", ".jpeg", ".png")
        image_files = [f for f in os.listdir(image_dir) if os.path.isfile(os.path.join(image_dir, f)) and f.lower().endswith(valid_exts)]

        paired_files = []
        unpaired_images = 0
        label_files = {os.path.splitext(f)[0] for f in os.listdir(label_dir) if os.path.isfile(os.path.join(label_dir, f)) and f.lower().endswith(".txt")}

        for img in image_files:
            base, ext = os.path.splitext(img)
            if base in label_files:
                paired_files.append((base, ext))
            else:
                unpaired_images += 1

        if unpaired_images > 0:
            self.master.after(0, self.update_log, f"⚠ ラベルがない画像が {unpaired_images} 件見つかりました。（スキップ）")

        if not paired_files:
            self.master.after(0, self.update_log, "ラベル付き画像が見つからなかったので終了。")
            return

        random.shuffle(paired_files)
        split_idx = int(len(paired_files) * split_ratio)
        train_set = paired_files[:split_idx]
        val_set = paired_files[split_idx:]

        def move_files(file_list, subset_image_dir, subset_label_dir, original_image_dir, original_label_dir):
            os.makedirs(subset_image_dir, exist_ok=True)
            os.makedirs(subset_label_dir, exist_ok=True)
            for base, ext in file_list:
                img_src = os.path.join(original_image_dir, base + ext)
                lbl_src = os.path.join(original_label_dir, base + ".txt")

                img_dst = os.path.join(subset_image_dir, base + ext)
                lbl_dst = os.path.join(subset_label_dir, base + ".txt")

                try:
                    if os.path.exists(img_src):
                        shutil.move(img_src, img_dst)
                    if os.path.exists(lbl_src):
                        shutil.move(lbl_src, lbl_dst)
                except Exception as e:
                    self.master.after(0, self.update_log, f"⚠ ファイルの移動に失敗しました ({base}{ext}): {e}")

        move_files(train_set, train_image_dir, train_label_dir, image_dir, label_dir)
        move_files(val_set, val_image_dir, val_label_dir, image_dir, label_dir)
        self.current_step += 1
        self.print_progress_inline()
        self.master.after(0, self.update_log, f"アノテーション処理完了 Train {len(train_set)}件 / Val {len(val_set)}件")

        self.generate_yaml(output_dir)

    def run_label_converter_gui(self, before, after):
        if not before or not after:
            messagebox.showerror("エラー", "Before/After のパスが未設定です。")
            return
        threading.Thread(target=self._run_label_converter_thread, args=(before, after), daemon=True).start()

    def _run_label_converter_thread(self, before, after):
        try:
            self.split_yolo_dataset_with_clone(before, after)
            self.master.after(0, self.update_log, "変換と分割処理が正常に完了しました。")
        except Exception as e:
            self.master.after(0, self.update_log, f"処理に失敗しました:\n{e}")

    def build_layout(self):
        self.top_bar = tk.Frame(self.master, bg="#282c34", height=50)
        self.top_bar.pack(fill="x", side="top")
        tk.Label(self.top_bar, text="Mosaic tool Developer", bg="#282c34", fg="white", font=("Quicksand", 16, "bold"), pady=10).pack(pady=5)

        self.sidebar = tk.Frame(self.master, bg="#21222c", width=self.sidebar_width)
        self.sidebar.pack(fill="y", side="left")
        self.sidebar.pack_propagate(0)

        self.main_area = tk.Frame(self.master, bg="#1e1e2e")
        self.main_area.pack(fill="both", expand=True, side="right")

        self.nav_button("🏠 Home", self.show_home)
        self.nav_button("📁 Labels Create", self.show_label_create)

    def nav_button(self, text, command):
        b = tk.Button(self.sidebar, text=text, command=command, bg="#2a2b3a", fg="white",
                      activebackground="#3b3f51", activeforeground="white", bd=0,
                      font=("Quicksand", 11), pady=12, relief="flat")
        b.pack(fill="x", pady=6, padx=10, ipady=4)

    def clear_main_area(self):
        for widget in self.main_area.winfo_children():
            widget.destroy()

    def show_home(self):
        self.clear_main_area()
        tk.Label(self.main_area, text="Welcome to Mosaic Developer Tool!", font=("Quicksand", 18, "bold"), bg="#1e1e2e", fg="white").pack(pady=40)
        tk.Label(self.main_area, text="Enjoy the label-studio", font=("Quicksand", 12), bg="#1e1e2e", fg="lightgray").pack()

    def show_label_create(self):
        self.clear_main_area()
        vars_ = {
            "labels_before": tk.StringVar(value=""),
            "labels_done": tk.StringVar(value="")
        }

        def select_folder(var, label):
            path = filedialog.askdirectory(title="Select Folder")
            if path:
                var.set(path)
                label.config(text=path)

        section = tk.Frame(self.main_area, bg="#1e1e2e")
        section.pack(pady=30)

        label_style = {"bg": "#2c2f38", "fg": "white", "anchor": "w", "width": 60, "padx": 10, "pady": 6, "bd": 0, "font": ("Quicksand", 10)}
        btn_style = {"font": ("Quicksand", 10, "bold"), "relief": "flat", "bd": 0, "padx": 12, "pady": 6}

        tk.Label(section, text="Labels Before", bg="#1e1e2e", fg="white", font=("Quicksand", 12)).grid(row=0, column=0, sticky="w")
        label1 = tk.Label(section, text=vars_["labels_before"].get() or "未設定", **label_style)
        label1.grid(row=1, column=0, sticky="ew")
        tk.Button(section, text="Select", command=lambda: select_folder(vars_["labels_before"], label1), bg="#3f51b5", fg="white", **btn_style).grid(row=1, column=1, padx=10)

        tk.Label(section, text="Labels Done", bg="#1e1e2e", fg="white", font=("Quicksand", 12)).grid(row=2, column=0, sticky="w", pady=(20, 0))
        label2 = tk.Label(section, text=vars_["labels_done"].get() or "未設定", **label_style)
        label2.grid(row=3, column=0, sticky="ew")
        tk.Button(section, text="Select", command=lambda: select_folder(vars_["labels_done"], label2), bg="#3f51b5", fg="white", **btn_style).grid(row=3, column=1, padx=10)

        btn_frame = tk.Frame(section, bg="#1e1e2e")
        btn_frame.grid(row=4, column=0, columnspan=2, pady=40)

        self.label_studio_button = tk.Button(btn_frame, text="LabelStudio Launch", command=self.launch_label_studio, bg="#8e8ee5", fg="black",
                                            font=("Quicksand", 12, "bold"), relief="flat", bd=0, padx=30, pady=10)
        self.label_studio_button.pack(pady=10)

        self.enable_button()

        def on_button_click_press(event):
            if self.label_studio_button['state'] != 'disabled':
                self.label_studio_button.config(bg="#7a7ad1")

        def on_button_click_release(event):
            if self.label_studio_button['state'] != 'disabled':
                self.enable_button()

        self.label_studio_button.bind("<ButtonPress-1>", on_button_click_press)
        self.label_studio_button.bind("<ButtonRelease-1>", on_button_click_release)

        tk.Button(btn_frame, text="Convert val/train", command=lambda: self.run_label_converter_gui(vars_["labels_before"].get(), vars_["labels_done"].get()), bg="#26c6da", fg="black",
                  font=("Quicksand", 12, "bold"), relief="flat", bd=0, padx=30, pady=10).pack(pady=10)

        self.log_label = tk.Label(self.main_area, text="", bg="#1e1e2e", fg="white", font=("Quicksand", 10), wraplength=800)
        self.log_label.pack(pady=10)

    def on_closing(self):
        if self.process and self.process.poll() is None:
            try:
                if os.name == 'nt':
                    subprocess.run(["taskkill", "/F", "/T", "/PID", str(self.process.pid)], check=False, capture_output=True, text=True)
                else:
                    self.process.terminate()
                    try:
                        self.process.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        print(f"プロセスが5秒以内に終了しませんでした。強制終了します...")
                        self.process.kill()
                        self.process.wait()
            except Exception as e:
                print(f"プロセスの終了に失敗しました: {e}")
        self.master.destroy()

def main():
    root = tk.Tk()
    app = DashboardApp(root)
    root.mainloop()

if __name__ == "__main__":
    main()