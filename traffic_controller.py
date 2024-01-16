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
    counter_index = 0  # 假设我们关注的是索引为 0 的计数器项

    # 使用控制器的 counter_read 方法从交换机获取计数器数据
    counter_data = controller.counter_read(my_counter, counter_index)

    # 解析并返回所需的统计数据
    # 注意：返回的数据结构取决于 P4Runtime API 的具体实现
    packet_count = counter_data.packet_count if counter_data is not None else 0
    byte_count = counter_data.byte_count if counter_data is not None else 0

    return packet_count, byte_count

def check_traffic_threshold(controller):
    traffic_stats = get_traffic_stats(controller, "traffic_counter")
    byte_count =  traffic_stats[1]
    if byte_count * 8 / 10 >= THRESHOLD_DROP:
        return "drop"
    elif byte_count * 8 / 10 >= THRESHOLD_LOAD_BALANCING:
        return "load_balance"
    else:
        return "normal"


def set_forwarding_rules(controllers, state):
    con = {1:controllers['s1'], 2:controllers['s2'], 3:controllers['s3']}
    # Reset grpc server
    con[1].reset_state()
    if state == "normal":
        # clear existing rules in switches s1 and s2
        con[1].table_clear('fwd_table')
        # add rules in switch s1
        con[1].table_add('fwd_table', 'forward', ['1'], ['2'])
        con[1].table_add('fwd_table', 'forward', ['2'], ['1'])
    elif state == "load_balance":
        # clear existing rules in switches s1 and s2
        con[1].table_clear('fwd_table')
        con[2].table_clear('fwd_table')

        # add rules in switch s1
        con[1].table_add('fwd_table', 'forward', ['1'], ['3'])
        con[1].table_add('fwd_table', 'forward', ['3'], ['1'])
        con[1].table_add('fwd_table', 'forward', ['1'], ['2'])
        con[1].table_add('fwd_table', 'forward', ['2'], ['1'])

        # add rules in switch s2
        con[2].table_add('fwd_table', 'forward', ['1'], ['2'])
        con[2].table_add('fwd_table', 'forward', ['2'], ['1'])

        #add rules in switch s3 这个端口名字不确定
        con[3].table_add('fwd_table', 'forward', ['2'], ['3'])
        con[3].table_add('fwd_table', 'forward', ['3'], ['2'])
    elif state == "drop":
        # 丢弃流量的规则
        # clear existing rules in switches s1 and s2
        con[1].table_clear('fwd_table')
        con[2].table_clear('fwd_table')

        con[1].table_add('fwd_table', 'drop',['1'],['2'])
        con[1].table_add('fwd_table', 'drop',['2'],['1'])

while True:
    for switch, controller in controllers.items():
        if switch == 's1':  # 只检查名为 's1' 的交换机
            state = check_traffic_threshold(controller)
            set_forwarding_rules(controllers, state)
    time.sleep(10)  # 每10秒检查一次
