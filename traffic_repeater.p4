#include <core.p4>
#include <v1model.p4>


#define CPU_PORT 255

struct metadata {
}

header ethernet_t {
    bit<48> dstAddr;
    bit<48> srcAddr;
    bit<16> etherType;
}

struct headers {
    ethernet_t ethernet;
}

counter my_counter {
    type: PACKETS_AND_BYTES;
    size: 1024;
}


parser MyParser(packet_in packet,
                out headers hdr,
                inout standard_metadata_t standard_metadata) {
    state start {
        packet.extract(hdr.ethernet);
        transition accept;
    }
}

control MyVerifyChecksum(inout headers hdr, inout metadata meta) {
    apply {  }
}

control MyIngress(inout headers hdr,
                  inout metadata meta,
                  inout standard_metadata_t standard_metadata) {
    // 转发表
    table fwd_table {
        key = {
            standard_metadata.ingress_port: exact;
        }
        actions = {
            forward; // 转发动作
            NoAction;
            drop;//丢弃动作
        }
        size = 1024; // 表的大小
        default_action = NoAction(); // 默认动作
    }

    // 转发动作
    action forward(bit<9> egress_port) {
        standard_metadata.egress_spec = egress_port;
        my_counter.count(0);
    }
    
    // 丢弃动作
    action drop() {
        mark_to_drop(standard_metadata);
    }

    // 应用转发逻辑
    apply {
        fwd_table.apply();
    }
}

control MyDeparser(packet_out packet, in headers hdr) {
    apply {

    /* Deparser not needed */

    }
}

// 控制器：校验和更新
control MyEgress(inout headers hdr,
                 inout metadata meta,
                 inout standard_metadata_t standard_metadata) {
    apply {  }
}

control MyComputeChecksum(inout headers  hdr, inout metadata meta) {
    apply { }
}

V1Switch(
MyParser(),
MyVerifyChecksum(),
MyIngress(),
MyEgress(),
MyComputeChecksum(),
MyDeparser()
) main;