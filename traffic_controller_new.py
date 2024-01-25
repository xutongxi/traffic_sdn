from p4utils.utils.helper import load_topo
from p4utils.utils.sswitch_p4runtime_API import SimpleSwitchP4RuntimeAPI
import logging
import time
logging.basicConfig(level=logging.DEBUG, format='%(message)s')


topo = load_topo('topo_repeater.json')
controllers = {}

for switch, data in topo.get_p4rtswitches().items():
    logging.debug("Connecting to switch %s, IP %s, grpc port %s"%(switch,data['grpc_ip'],data['grpc_port']))
    controllers[switch] = SimpleSwitchP4RuntimeAPI(data['device_id'], data['grpc_port'],
                                                  grpc_ip=data['grpc_ip'],
                                                  p4rt_path=data['p4rt_path'],
                                                  json_path=data['json_path'])

con = {1:controllers['s1'], 2:controllers['s2'], 3:controllers['s3']}

THRESHOLD_LOAD_BALANCING = 512 * 1024  # 512 Kbps
THRESHOLD_DROP = 768 * 1024  # 768 Kbps

con[1].reset_state()
con[2].reset_state()
con[3].reset_state()

con[1].table_clear('fwd_table')
con[2].table_clear('fwd_table')
con[3].table_clear('fwd_table')

con[1].table_add('fwd_table', 'forward', ['1'], ['2'])
con[1].table_add('fwd_table', 'forward', ['2'], ['1'])

con[2].table_add('fwd_table', 'forward', ['1'], ['2'])
con[2].table_add('fwd_table', 'forward', ['2'], ['1'])

con[3].table_add('fwd_table', 'forward', ['2'], ['3'])
con[3].table_add('fwd_table', 'forward', ['3'], ['2'])

def get_traffic_stats(controller, my_counter):
    """
    从 P4 交换机获取指定计数器的统计数据。

    :param controller: P4 交换机的控制器实例。
    :param counter_name: 计数器的名称，例如 'my_counter'。
    :return: 返回一个包含包数量和字节总数的元组。
    """
    port_number = 1

    # 使用控制器的 counter_read 方法从交换机获取计数器数据
    counter_data = controller.counter_read(my_counter, port_number)

   # 检查 counter_data 是否为 None
    if counter_data is None:
        return 0, 0

    # 解析元组中的数据
    packet_count, byte_count = counter_data

    return packet_count, byte_count

def check_traffic_threshold(controller, byte_count):
    traffic_stats = get_traffic_stats(controller, "port_counter")
    byte_count_new = traffic_stats[1]
    volume = byte_count_new - byte_count
    byte_count = byte_count_new

    if volume * 8 / 10 >= THRESHOLD_DROP:
        return "drop", byte_count
    elif volume * 8 / 10 >= THRESHOLD_LOAD_BALANCING:
        return "load_balance", byte_count
    else:
        return "normal", byte_count


def set_forwarding_rules(controllers, state):
    con = controllers['s1']
    # Reset grpc server
    con.reset_state()
    if state == "normal":
        # clear existing rules in switches s1 and s2
        con.table_clear('fwd_table')
        # add rules in switch s1
        con.table_add('fwd_table', 'forward', ['1'], ['2'])
        con.table_add('fwd_table', 'forward', ['2'], ['1'])
    elif state == "load_balance":
        # clear existing rules in switches s1 and s2
        con.table_clear('fwd_table')

        # add rules in switch s1
        con.table_add('fwd_table', 'forward', ['1'], ['3'])
        con.table_add('fwd_table', 'forward', ['3'], ['1'])
        con.table_add('fwd_table', 'forward', ['1'], ['2'])
        con.table_add('fwd_table', 'forward', ['2'], ['1'])

    elif state == "drop":
        # 丢弃流量的规则
        # clear existing rules in switches s1 and s2
        con.table_clear('fwd_table')

        con.table_add('fwd_table', 'drop',['1'],['2'])
        con.table_add('fwd_table', 'drop',['2'],['1'])


traffic_stats = get_traffic_stats(con[1], "port_counter")
byte_count =  traffic_stats[1]

while True:
    for switch, controller in controllers.items():
        if switch == 's1':  # 只检查名为 's1' 的交换机
            state, updated_byte_count = check_traffic_threshold(controller, byte_count)
            byte_count = updated_byte_count
            set_forwarding_rules(controllers, state)
    time.sleep(10)  # 每10秒检查一次
