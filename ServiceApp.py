import sqlite3
import tkinter as tk
from tkinter import ttk, messagebox
from datetime import datetime, timedelta

# ==========================================================
# --- 全局常量和配置 ---
# ==========================================================
DATABASE_NAME = 'auto_service_log.db'

# 时间表配置
START_TIME_HOUR = 8  # 8:00 AM
END_TIME_HOUR = 17   # 5:00 PM (即 17:00)
TIME_SLOTS = []
# 生成从 8:30 到 17:30 的时间槽
for h in range(START_TIME_HOUR, END_TIME_HOUR + 1):
    for m in [30, 0] if h == START_TIME_HOUR else [0, 30]:
        if h == END_TIME_HOUR and m > 30: continue
        if h == START_TIME_HOUR and m == 0: continue # 从 8:30 开始
        
        TIME_SLOTS.append(f"{h:02d}:{m:02d}")

# 日历年份配置 (2026-2050)
CALENDAR_YEARS = [str(year) for year in range(2026, 2051)]


# ==========================================================
# --- 数据库初始化 ---
# ==========================================================
def setup_database():
    """连接数据库并创建必要的表格。"""
    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()

    # 1. 预约表 (Appointments)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS appointments (
            id INTEGER PRIMARY KEY,
            date TEXT NOT NULL,
            time TEXT NOT NULL,
            client_name TEXT,
            phone TEXT,
            plate_number TEXT NOT NULL,
            service_type TEXT
        )
    ''')

    # 2. 维修历史表 (Maintenance History)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS history (
            id INTEGER PRIMARY KEY,
            date TEXT NOT NULL,
            plate_number TEXT NOT NULL,
            client_phone TEXT,
            description TEXT,
            cost REAL
        )
    ''')

    conn.commit()
    return conn


# ==========================================================
# --- 主应用程序类 ---
# ==========================================================
class ServiceLogApp:
    def __init__(self, root):
        self.root = root
        self.root.title("🚗 汽修厂服务日志与预约系统")
        self.conn = setup_database()
        
        # 当前显示的时间表日期状态
        self.current_date = datetime.now().date()
        
        # 创建一个Notebook（标签页）来分隔功能
        self.notebook = ttk.Notebook(root)
        self.notebook.pack(pady=10, padx=10, expand=True, fill="both")

        # --- 标签页 1: 每周预约时间表视图 ---
        self.appointment_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.appointment_frame, text="📅 每周预约")
        self.setup_appointment_view()

        # --- 标签页 2: 历史查询与记录 ---
        self.history_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.history_frame, text="🔍 历史查询")
        self.setup_history_search()
        
        # 初始加载数据 (时间表不需要，它会在绘制网格后自动加载)


    # ==========================================================
    # 可视化时间表视图方法
    # ==========================================================
    def setup_appointment_view(self):
        """设置每周时间表视图 (Canvas 实现)。"""
        
        # --- 控件：日期导航和年份选择 ---
        nav_frame = ttk.Frame(self.appointment_frame)
        nav_frame.pack(fill='x', pady=5)
        
        # 年份选择下拉菜单
        self.selected_year = tk.StringVar(value=str(self.current_date.year))
        ttk.Label(nav_frame, text="年份:").pack(side='left', padx=5)
        self.year_combo = ttk.Combobox(nav_frame, textvariable=self.selected_year, values=CALENDAR_YEARS, width=6, state="readonly")
        self.year_combo.pack(side='left', padx=5)
        self.year_combo.bind("<<ComboboxSelected>>", self.change_schedule_view)
        
        # 导航按钮
        ttk.Button(nav_frame, text="< 上一周", command=lambda: self.navigate_week(-1)).pack(side='left', padx=10)
        ttk.Button(nav_frame, text="本周", command=lambda: self.navigate_week(0)).pack(side='left', padx=10)
        ttk.Button(nav_frame, text="下一周 >", command=lambda: self.navigate_week(1)).pack(side='left', padx=10)
        
        # --- 时间表容器 ---
        self.schedule_container = ttk.Frame(self.appointment_frame)
        self.schedule_container.pack(expand=True, fill="both", pady=5)

        # 1. 顶部日期标签和周视图
        self.date_labels = []
        for i in range(8): # 0列留给时间，1-7列是日期
            day_frame = ttk.Frame(self.schedule_container)
            day_frame.grid(row=0, column=i, sticky="nsew")
            self.schedule_container.grid_columnconfigure(i, weight=1 if i > 0 else 0)
            
            # 存储标签引用
            if i > 0:
                day_name_label = ttk.Label(day_frame, text="", font=('Arial', 10, 'bold'))
                day_name_label.pack()
                date_label = ttk.Label(day_frame, text="", font=('Arial', 9))
                date_label.pack()
                self.date_labels.append((day_name_label, date_label))

        # 2. 左侧时间轴 (在 navigate_week 中绘制)
        for i in range(len(TIME_SLOTS)):
            self.schedule_container.grid_rowconfigure(i + 1, weight=1)

        # 3. Canvas 时间表区域 (用于绘制预约方块)
        self.schedule_canvas = tk.Canvas(self.schedule_container, bg='white', borderwidth=1, relief="solid")
        self.schedule_canvas.grid(row=1, column=1, rowspan=len(TIME_SLOTS), columnspan=7, sticky="nsew")
        
        # 绘制背景网格线
        self.schedule_canvas.bind('<Configure>', self.draw_schedule_grid)
        
        # 4. 新增预约按钮
        btn_add = ttk.Button(self.appointment_frame, text="➕ 新增预约", command=self.open_add_appointment_window)
        btn_add.pack(pady=5)
        
        # 初始化显示本周数据
        self.update_schedule_labels()
        self.draw_time_axis()

    def draw_time_axis(self):
        """绘制左侧的时间轴标签。"""
        # 移除旧的时间标签 (除了日期行和 Canvas)
        for widget in self.schedule_container.grid_slaves(column=0):
            if widget not in self.date_labels: # 确保不是日期行
                widget.destroy()
        
        # 绘制新的时间标签
        for i, time_str in enumerate(TIME_SLOTS):
            ttk.Label(self.schedule_container, text=time_str, font=('Arial', 9)).grid(row=i + 1, column=0, sticky="nse", padx=5)


    def update_schedule_labels(self):
        """更新顶部的日期标签以匹配 self.current_date 所在周。"""
        
        # 找到当前日期所在周的周一
        start_of_week = self.current_date - timedelta(days=self.current_date.weekday())
        
        day_names = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]

        for i in range(7):
            date_to_display = start_of_week + timedelta(days=i)
            day_name, date_label = self.date_labels[i]
            
            day_name.config(text=day_names[i])
            date_label.config(text=date_to_display.strftime("%Y-%m-%d"))

        # 重新绘制网格和预约
        self.draw_schedule_grid()

    def navigate_week(self, offset):
        """向前或向后导航一周，或回到本周。"""
        if offset == 0:
            self.current_date = datetime.now().date()
        else:
            self.current_date += timedelta(weeks=offset)
        
        self.selected_year.set(str(self.current_date.year))
        self.update_schedule_labels()

    def change_schedule_view(self, event=None):
        """当年份选择改变时，更新视图到该年份的今天。"""
        try:
            target_year = int(self.selected_year.get())
            # 导航到新选年份的今天
            self.current_date = self.current_date.replace(year=target_year)
            self.update_schedule_labels()
        except ValueError:
            pass # 忽略无效选择

    def draw_schedule_grid(self, event=None):
        """根据 Canvas 尺寸绘制时间表网格线和时间槽"""
        if not self.schedule_canvas.winfo_width():
            return
            
        self.schedule_canvas.delete("all") # 清空旧的绘制内容，但不影响绑定的事件

        canvas_width = self.schedule_canvas.winfo_width()
        canvas_height = self.schedule_canvas.winfo_height()
        
        num_days = 7
        num_slots = len(TIME_SLOTS)
        
        day_width = canvas_width / num_days
        slot_height = canvas_height / num_slots

        # 绘制垂直线 (分隔每天)
        for i in range(1, num_days):
            x = i * day_width
            self.schedule_canvas.create_line(x, 0, x, canvas_height, fill="lightgray")

        # 绘制水平线 (分隔时间槽)
        for i in range(1, num_slots):
            y = i * slot_height
            self.schedule_canvas.create_line(0, y, canvas_width, y, fill="#EEEEEE", dash=(2, 2))
            
        # 重新加载预约数据，将它们画在新的网格上
        self.load_appointments()


    def load_appointments(self):
        """从数据库加载预约数据并绘制在 Canvas 上。"""
        
        self.schedule_canvas.delete("appointment_block") # 清空旧的预约方块

        canvas_width = self.schedule_canvas.winfo_width()
        canvas_height = self.schedule_canvas.winfo_height()
        if not canvas_width or not canvas_height:
            return

        num_days = 7
        num_slots = len(TIME_SLOTS)
        day_width = canvas_width / num_days
        slot_height = canvas_height / num_slots

        # 找到当前显示的周一
        start_of_week = self.current_date - timedelta(days=self.current_date.weekday())
        
        cursor = self.conn.cursor()
        cursor.execute("SELECT date, time, client_name, phone, plate_number, service_type FROM appointments")
        
        for row in cursor.fetchall():
            date_str, time_str, client, phone, plate, service = row
            
            try:
                appt_date = datetime.strptime(date_str, "%Y-%m-%d").date()
                appt_time_obj = datetime.strptime(time_str, "%H:%M")
                appt_time_minutes = appt_time_obj.hour * 60 + appt_time_obj.minute
            except ValueError:
                continue

            # 1. 计算预约块的日坐标 (X轴)
            day_diff = (appt_date - start_of_week).days
            
            # 仅显示当前周的预约
            if 0 <= day_diff < 7:
                
                # 2. 找到最接近的时间槽
                slot_index = -1
                for i, t in enumerate(TIME_SLOTS):
                    h, m = map(int, t.split(':'))
                    slot_minutes = h * 60 + m
                    if appt_time_minutes == slot_minutes:
                        slot_index = i
                        break
                
                if slot_index != -1:
                    
                    # 3. 绘制预约方块
                    x0 = day_diff * day_width
                    y0 = slot_index * slot_height
                    x1 = (day_diff + 1) * day_width
                    y1 = (slot_index + 1) * slot_height # 默认占一个时间槽 (30分钟)

                    # 颜色和标签
                    color = "lightblue"
                    self.schedule_canvas.create_rectangle(x0 + 1, y0 + 1, x1 - 1, y1 - 1, fill=color, tags="appointment_block")
                    
                    # 绘制文字 (车牌号, 客户名, 服务项目)
                    text_content = f"{plate}\n{client}\n{service}"
                    self.schedule_canvas.create_text(
                        x0 + day_width / 2, y0 + slot_height / 2,
                        text=text_content,
                        fill="black",
                        justify=tk.CENTER,
                        tags="appointment_block"
                    )
                    
                    # 绑定点击事件
                    appt_info = (date_str, time_str, client, phone, plate, service)
                    self.schedule_canvas.tag_bind("appointment_block", "<Button-1>", lambda e, info=appt_info: self.show_appointment_details(info))

    def show_appointment_details(self, info):
        """显示预约详情，未来可用于编辑或删除"""
        date_str, time_str, client, phone, plate, service = info
        messagebox.showinfo("预约详情",
            f"日期: {date_str}\n时间: {time_str}\n客户: {client}\n电话: {phone}\n车牌: {plate}\n项目: {service}")
    
    # *** 新增预约的完整实现 (与时间表配合) ***
    def open_add_appointment_window(self):
        """打开新增预约的对话框"""
        
        self.add_win = tk.Toplevel(self.root)
        self.add_win.title("新增客户预约")
        
        # 字段标签和输入框定义
        fields = ["日期 (YYYY-MM-DD):", "时间 (HH:MM):", "客户名:", "电话:", "车牌号:", "服务项目:"]
        self.entries = {}
        
        frame = ttk.Frame(self.add_win, padding="10")
        frame.pack(padx=10, pady=10)

        for i, field in enumerate(fields):
            ttk.Label(frame, text=field).grid(row=i, column=0, sticky="w", pady=5)
            
            # 特别处理时间输入为下拉菜单，确保输入时间是 TIME_SLOTS 中的有效值
            if "时间" in field:
                var = tk.StringVar()
                combo = ttk.Combobox(frame, textvariable=var, values=TIME_SLOTS, state="readonly", width=27)
                combo.grid(row=i, column=1, padx=10, pady=5)
                self.entries[field] = var
                # 默认值设置为第一个时间槽
                if TIME_SLOTS:
                    var.set(TIME_SLOTS[0])
            else:
                var = tk.StringVar()
                entry = ttk.Entry(frame, textvariable=var, width=30)
                entry.grid(row=i, column=1, padx=10, pady=5)
                self.entries[field] = var

        # 保存按钮
        btn_save = ttk.Button(self.add_win, text="保存预约", command=self.save_appointment)
        btn_save.pack(pady=10)

        self.add_win.grab_set()
        self.add_win.focus_set()
        self.root.wait_window(self.add_win)


    def save_appointment(self):
        """将用户输入的数据存入数据库"""
        
        date = self.entries["日期 (YYYY-MM-DD):"].get().strip()
        time = self.entries["时间 (HH:MM):"].get().strip()
        client_name = self.entries["客户名:"].get().strip()
        phone = self.entries["电话:"].get().strip()
        plate_number = self.entries["车牌号:"].get().strip()
        service_type = self.entries["服务项目:"].get().strip()

        # 简单的数据校验
        if not all([date, time, client_name, plate_number]):
            messagebox.showwarning("输入错误", "日期、时间、客户名和车牌号为必填项。")
            return
            
        try:
            # 校验日期格式
            datetime.strptime(date, "%Y-%m-%d")
            
            cursor = self.conn.cursor()
            query = """
                INSERT INTO appointments (date, time, client_name, phone, plate_number, service_type) 
                VALUES (?, ?, ?, ?, ?, ?)
            """
            cursor.execute(query, (date, time, client_name, phone, plate_number, service_type))
            self.conn.commit()
            
            messagebox.showinfo("成功", "预约已成功保存！")
            
            # 刷新时间表并关闭窗口
            self.update_schedule_labels() # 调用更新函数来触发重绘
            self.add_win.destroy()
            
        except ValueError:
            messagebox.showerror("输入错误", "日期格式不正确，请使用 YYYY-MM-DD 格式。")
        except Exception as e:
            messagebox.showerror("数据库错误", f"保存预约失败: {e}")
            
    # ==========================================================
    # 历史查询相关方法 (保持不变)
    # ==========================================================

    def setup_history_search(self):
        # 搜索框和按钮
        search_frame = ttk.Frame(self.history_frame)
        search_frame.pack(fill='x', pady=5)
        
        ttk.Label(search_frame, text="车牌/电话:").pack(side='left', padx=5)
        self.search_entry = ttk.Entry(search_frame, width=30)
        self.search_entry.pack(side='left', padx=5, expand=True, fill='x')
        self.search_entry.bind('<Return>', lambda e: self.perform_search())
        
        btn_search = ttk.Button(search_frame, text="查找历史", command=self.perform_search)
        btn_search.pack(side='left', padx=5)
        
        # 历史记录展示 Treeview
        history_cols = ('date', 'plate', 'phone', 'description', 'cost')
        self.history_tree = ttk.Treeview(self.history_frame, columns=history_cols, show='headings')
        self.history_tree.pack(expand=True, fill="both", pady=5)

        history_headings = {'date': '日期', 'plate': '车牌号', 'phone': '客户电话',
                            'description': '维修项目描述', 'cost': '费用 (RMB)'}
        for col, text in history_headings.items():
            self.history_tree.heading(col, text=text)
            self.history_tree.column(col, width=100 if col not in ['description'] else 250, anchor='center')

        # 增加新增历史记录按钮
        btn_add_history = ttk.Button(self.history_frame, text="➕ 新增维修记录", command=self.open_add_history_window)
        btn_add_history.pack(pady=5)


    def perform_search(self):
        """执行历史记录查询"""
        search_term = self.search_entry.get().strip()
        if not search_term:
            messagebox.showwarning("输入提示", "请输入车牌号或客户电话进行查询。")
            return

        for item in self.history_tree.get_children():
            self.history_tree.delete(item)

        cursor = self.conn.cursor()
        
        query = """
            SELECT date, plate_number, client_phone, description, cost 
            FROM history 
            WHERE plate_number LIKE ? OR client_phone LIKE ? 
            ORDER BY date DESC
        """
        search_like = f'%{search_term}%'
        cursor.execute(query, (search_like, search_like))
        
        results = cursor.fetchall()
        
        if not results:
            messagebox.showinfo("查询结果", f"未找到与 '{search_term}' 相关的历史记录。")
            
        for row in results:
            self.history_tree.insert('', 'end', values=row)

    
    # *** 新增维修历史的完整实现 ***
    def open_add_history_window(self):
        """打开新增维修历史记录的对话框"""
        
        self.history_win = tk.Toplevel(self.root)
        self.history_win.title("新增维修历史")
        
        fields = ["日期 (YYYY-MM-DD):", "车牌号*:", "客户电话:", "维修项目描述*:", "费用 (RMB)*:"]
        self.history_entries = {}
        
        frame = ttk.Frame(self.history_win, padding="10")
        frame.pack(padx=10, pady=10)

        for i, field in enumerate(fields):
            ttk.Label(frame, text=field).grid(row=i, column=0, sticky="w", pady=5)
            
            var = tk.StringVar()
            if "描述" in field:
                text_widget = tk.Text(frame, height=5, width=30)
                text_widget.grid(row=i, column=1, padx=10, pady=5)
                self.history_entries[field] = text_widget
            else:
                entry = ttk.Entry(frame, textvariable=var, width=30)
                entry.grid(row=i, column=1, padx=10, pady=5)
                self.history_entries[field] = var

        # 保存按钮
        btn_save = ttk.Button(self.history_win, text="保存记录", command=self.save_history)
        btn_save.pack(pady=10)

        self.history_win.grab_set()
        self.history_win.focus_set()
        self.root.wait_window(self.history_win)


    def save_history(self):
        """将用户输入的数据存入历史记录数据库"""
        
        date = self.history_entries["日期 (YYYY-MM-DD):"].get().strip()
        plate_number = self.history_entries["车牌号*:"].get().strip()
        client_phone = self.history_entries["客户电话:"].get().strip()
        description = self.history_entries["维修项目描述*:"]
        cost = self.history_entries["费用 (RMB)*:"].get().strip()
        
        description_text = description.get("1.0", tk.END).strip()

        if not all([date, plate_number, description_text, cost]):
            messagebox.showwarning("输入错误", "带星号 (*) 的字段为必填项。")
            return

        try:
            cost_value = float(cost)
            datetime.strptime(date, "%Y-%m-%d")
        except ValueError:
            messagebox.showwarning("输入错误", "日期格式或费用数值格式不正确。")
            return

        try:
            cursor = self.conn.cursor()
            query = """
                INSERT INTO history (date, plate_number, client_phone, description, cost) 
                VALUES (?, ?, ?, ?, ?)
            """
            cursor.execute(query, (date, plate_number, client_phone, description_text, cost_value))
            self.conn.commit()
            
            messagebox.showinfo("成功", "维修历史记录已成功保存！")
            
            self.history_win.destroy()
            
        except Exception as e:
            messagebox.showerror("数据库错误", f"保存记录失败: {e}")

# --- 运行主程序 ---
if __name__ == "__main__":
    
    # 示例数据插入
    conn = setup_database()
    cursor = conn.cursor()
    
    # 清空旧数据以避免重复插入
    cursor.execute("DELETE FROM appointments")
    cursor.execute("DELETE FROM history")
    
    # 插入示例预约 (使用明天的日期，便于在日历上看到)
    tomorrow = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
    next_week = (datetime.now() + timedelta(days=8)).strftime("%Y-%m-%d")
    
    cursor.execute("INSERT INTO appointments VALUES (NULL, ?, '09:00', '王先生', '13812345678', '浙A88888', '常规保养')", (tomorrow,))
    cursor.execute("INSERT INTO appointments VALUES (NULL, ?, '14:30', '赵女士', '13998765432', '沪B12345', '更换轮胎')", (next_week,))
    
    # 插入示例历史记录
    cursor.execute("INSERT INTO history VALUES (NULL, '2025-05-10', '浙A88888', '13812345678', '更换机油滤清器、四轮定位', 850.00)")
    cursor.execute("INSERT INTO history VALUES (NULL, '2025-08-15', '浙A88888', '13812345678', '刹车片更换', 600.00)")
    
    conn.commit()
    conn.close()


    root = tk.Tk()
    app = ServiceLogApp(root)
    root.mainloop()
