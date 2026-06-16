import pandas as pd
import numpy as np
from tqdm import tqdm

def parse_traffic_types_from_stats(stats_file):
    """
    Parse the NrDlPdcpStatsE2E.txt file to determine traffic types per RNTI based on TxBytes.
    TxBytes == 780000 -> ULL Traffic
    TxBytes == 7692000 -> BE Traffic
    Returns a dictionary mapping RNTI to its (Traffic_Type, SLA_Threshold_ms).
    """
    print("[Phase 0/4] Parsing RNTI traffic types from E2E Stats...")
    
    # Read the text file treating any whitespace as delimiter
    stats_df = pd.read_csv(stats_file, sep=r'\s+', comment='%', names=[
        'start(s)', 'end(s)', 'CellId', 'IMSI', 'RNTI', 'LCID', 'nTxPDUs', 
        'TxBytes', 'nRxPDUs', 'RxBytes', 'delay(s)', 'stdDev(s)', 'min(s)', 
        'max(s)', 'PduSize', 'stdDev', 'min', 'max'
    ])
    
    rnti_traffic_map = {}
    for _, row in stats_df.iterrows():
        rnti = row['RNTI']
        tx_bytes = row['TxBytes']
        
        if tx_bytes == 780000:
            # ULL Traffic (SLA: 8ms)
            rnti_traffic_map[rnti] = ('ULL', 8.0)
        elif tx_bytes == 7692000:
            # BE Traffic (SLA: 100ms)
            rnti_traffic_map[rnti] = ('BE', 100.0)
        else:
            # 기본/예외 처리
            rnti_traffic_map[rnti] = ('Unknown', 100.0)
            
    print(f" -> Successfully mapped {len(rnti_traffic_map)} RNTIs to their traffic types.")
    return rnti_traffic_map


def build_event_log(input_file, stats_file, output_file):
    """
    Build an Event Log from the merged traces CSV file for Predictive Process Monitoring (PPM).
    Utilizes NrDlPdcpStatsE2E.txt to assign static Traffic Types and SLA Thresholds per RNTI.
    """
    # ==========================================
    # Phase 0: Map RNTIs to Traffic Types
    # ==========================================
    rnti_map = parse_traffic_types_from_stats(stats_file)
    
    # ==========================================
    # Phase 1: Data Preparation and Cleansing
    # ==========================================
    print("\n[Phase 1/4] Loading and cleansing data...")
    df = pd.read_csv(input_file)
    initial_rows = len(df)
    
    df['Time'] = pd.to_numeric(df['Time'], errors='coerce')
    df['delay(s)'] = pd.to_numeric(df['delay(s)'], errors='coerce')
    
    if 'packetSize' in df.columns:
        df['packetSize'] = pd.to_numeric(df['packetSize'], errors='coerce')
    
    # Remove meaningless system broadcast packets and common RNTIs
    broadcast_msgs = ['MIB', 'SIB1']
    invalid_rntis = [0, 65535]
    df = df[~df['MsgType'].isin(broadcast_msgs)]
    df = df[~df['RNTI'].isin(invalid_rntis)]
    
    # Remove uplink control messages and channel state reports
    ul_ctrl_msgs = ['UL_DCI', 'UL_UCI', 'SRS', 'CQI', 'DL_CQI']
    df = df[~df['MsgType'].isin(ul_ctrl_msgs)]
    
    print(f" -> Phase 1 Complete: Filtered rows from {initial_rows} to {len(df)}")
    
    # ==========================================
    # Phase 2: Flattening Packet Lifecycle (Sub-case Identification)
    # ==========================================
    print("\n[Phase 2/4] Flattening lifecycle and generating Case IDs...")
    
    pdcp_tx = df[df['Entity'] == 'gNB PDCP Txed'].copy()
    pdcp_tx = pdcp_tx.sort_values(by=['RNTI', 'Time'])
    pdcp_tx['Virtual_SN'] = pdcp_tx.groupby('RNTI').cumcount() + 1
    pdcp_tx['Case_ID'] = pdcp_tx['RNTI'].astype(str) + "_" + pdcp_tx['Virtual_SN'].astype(str)
    
    rx_pdcp = df[df['Entity'] == 'UE PDCP Rxed'].copy()
    rx_pdcp['Calculated_Tx_Time'] = rx_pdcp['Time'] - rx_pdcp['delay(s)']
    
    total_cases = len(pdcp_tx)
    print(f" -> Phase 2 Complete: Identified {total_cases} unique packet sub-cases.")
    
    # ==========================================
    # Phase 3: Activity Construction and Timeline Mapping
    # ==========================================
    print("\n[Phase 3/4] Constructing Activities and Mapping Timeline...")
    
    prefix_events = {}
    for rnti, group in df.groupby('RNTI'):
        rach = group[group['MsgType'] == 'RACH_PREAMBLE']
        rar = group[group['MsgType'] == 'RAR']
        prefix_events[rnti] = {
            'Admission_Request_Time': rach['Time'].min() if not rach.empty else np.nan,
            'Admission_Accept_Time': rar['Time'].min() if not rar.empty else np.nan
        }
    
    dci_logs = df[df['Entity'] == 'DL DCI Rxed'].copy()
    rlc_tx_logs = df[df['Entity'] == 'gNB RLC Txed'].copy()
    rlc_rx_logs = df[df['Entity'] == 'UE RLC Rxed'].copy()
    
    event_log_rows = []
    
    for idx, row in tqdm(pdcp_tx.iterrows(), total=total_cases, desc="Mapping Timeline", unit="case"):
        case_id = row['Case_ID']
        rnti = row['RNTI']
        tx_time = row['Time']
        pkt_size = row.get('packetSize', np.nan) 
        
        # Look up Traffic Type and SLA threshold from the Phase 0 map
        traffic_info = rnti_map.get(rnti, ('Unknown', 100.0))
        traffic_type = traffic_info[0]
        sla_threshold_ms = traffic_info[1]
        
        case_activities = []
        
        # --- 1. Prefix Events ---
        prefix = prefix_events.get(rnti, {})
        req_time = prefix.get('Admission_Request_Time')
        acc_time = prefix.get('Admission_Accept_Time')
        
        if pd.notna(req_time):
            case_activities.append({'Case_ID': case_id, 'RNTI': rnti, 'Activity': 'Admission_Request', 'Time': req_time})
        if pd.notna(acc_time):
            case_activities.append({'Case_ID': case_id, 'RNTI': rnti, 'Activity': 'Admission_Accept', 'Time': acc_time})
            
        # --- 2. Packet-specific Independent Events ---
        rnti_dcis = dci_logs[(dci_logs['RNTI'] == rnti) & (dci_logs['Time'] >= tx_time - 0.05) & (dci_logs['Time'] <= tx_time + 0.05)]
        dci_time = rnti_dcis['Time'].min() if not rnti_dcis.empty else np.nan
        if pd.notna(dci_time):
            case_activities.append({'Case_ID': case_id, 'RNTI': rnti, 'Activity': 'DL_Resource_Allocation', 'Time': dci_time})
            
        case_activities.append({'Case_ID': case_id, 'RNTI': rnti, 'Activity': 'DL_PDCP_Enqueue', 'Time': tx_time})
        
        tolerance = 0.01 
        rnti_rlc_tx = rlc_tx_logs[(rlc_tx_logs['RNTI'] == rnti) & (rlc_tx_logs['Time'] >= tx_time) & (rlc_tx_logs['Time'] <= tx_time + tolerance)]
        rlc_tx_time = rnti_rlc_tx['Time'].min() if not rnti_rlc_tx.empty else np.nan
        if pd.notna(rlc_tx_time):
            case_activities.append({'Case_ID': case_id, 'RNTI': rnti, 'Activity': 'DL_RLC_Tx', 'Time': rlc_tx_time})
            
        rnti_rlc_rx = rlc_rx_logs[(rlc_rx_logs['RNTI'] == rnti) & (rlc_rx_logs['Time'] >= tx_time) & (rlc_rx_logs['Time'] <= tx_time + tolerance)]
        rlc_rx_time = rnti_rlc_rx['Time'].min() if not rnti_rlc_rx.empty else np.nan
        if pd.notna(rlc_rx_time):
            case_activities.append({'Case_ID': case_id, 'RNTI': rnti, 'Activity': 'DL_RLC_Rx', 'Time': rlc_rx_time})
            
        # --- 3. End Event Determination (Success vs Fail) ---
        rnti_pdcp_rx = rx_pdcp[(rx_pdcp['RNTI'] == rnti) & (abs(rx_pdcp['Calculated_Tx_Time'] - tx_time) < tolerance)]
        
        packet_delay = np.nan
        if not rnti_pdcp_rx.empty:
            rx_record = rnti_pdcp_rx.iloc[0]
            rx_time = rx_record['Time']
            packet_delay = rx_record['delay(s)']
            case_activities.append({'Case_ID': case_id, 'RNTI': rnti, 'Activity': 'DL_Data_Received', 'Time': rx_time, 'Delay': packet_delay})
        else:
            timeout_time = tx_time + 0.100  
            case_activities.append({'Case_ID': case_id, 'RNTI': rnti, 'Activity': 'DL_Data_Failed', 'Time': timeout_time, 'Delay': np.nan})
            
        # Apply extracted attributes
        for act in case_activities:
            act['Packet_Size_Byte'] = pkt_size
            act['Traffic_Type'] = traffic_type
            act['SLA_Threshold_ms'] = sla_threshold_ms
            
        case_activities = sorted(case_activities, key=lambda x: x['Time'])
        event_log_rows.extend(case_activities)
        
    event_log = pd.DataFrame(event_log_rows)
    print(f" -> Phase 3 Complete: Generated {len(event_log)} activity rows.")
    
    # ==========================================
    # Phase 4: PPM Feature Engineering & Labeling
    # ==========================================
    
    print("\n[Phase 4/4] Feature Engineering and Labeling...")
    activity_order = {
        'Admission_Request': 1,
        'Admission_Accept': 2,
        'DL_Resource_Allocation': 3,
        'DL_PDCP_Enqueue': 4,
        'DL_RLC_Tx': 5,
        'DL_RLC_Rx': 6,
        'DL_Data_Received': 7,
        'DL_Data_Failed': 7
    }
    
    # Add logical column order by mapping
    event_log['Activity_Order'] = event_log['Activity'].map(activity_order)
    
    # Sorted with the orter Case_ID, Time, Activity_Order
    event_log = event_log.sort_values(['Case_ID', 'Time', 'Activity_Order']).reset_index(drop=True)
    
    # remove temporary column
    event_log = event_log.drop(columns=['Activity_Order'])

    final_features = []
    grouped_event_log = event_log.groupby('Case_ID')
    
    for case_id, group in tqdm(grouped_event_log, total=len(grouped_event_log), desc="Extracting Features", unit="case"):
        # group = group.sort_values('Time').reset_index(drop=True) sort with time
        
        acc_time = group.loc[group['Activity'] == 'Admission_Accept', 'Time'].min()
        dci_time = group.loc[group['Activity'] == 'DL_Resource_Allocation', 'Time'].min()
        
        time_since_admission = np.nan
        if pd.notna(acc_time) and pd.notna(dci_time):
            time_since_admission = dci_time - acc_time
            
        group['Time_since_Last_Activity'] = group['Time'].diff().fillna(0)
        
        final_activity_row = group.iloc[-1]
        final_activity = final_activity_row['Activity']
        delay_val = final_activity_row.get('Delay', np.nan)
        sla_threshold_ms = final_activity_row['SLA_Threshold_ms']
        
        # --- SLA 위반 판별 로직 ---
        sla_violation = 0
        if final_activity == 'DL_Data_Failed':
            sla_violation = 1
        elif final_activity == 'DL_Data_Received' and pd.notna(delay_val):
            if (delay_val * 1000) > sla_threshold_ms:
                sla_violation = 1
            
        group['Time_since_Admission'] = time_since_admission
        group['SLA_Violation'] = sla_violation
        
        final_features.append(group)

    final_event_log = pd.concat(final_features, ignore_index=True)
    
    cols = ['Case_ID', 'RNTI', 'Traffic_Type', 'SLA_Threshold_ms', 'Activity', 'Time', 
            'Time_since_Last_Activity', 'Time_since_Admission', 'Packet_Size_Byte', 'Delay', 'SLA_Violation']
    cols = [c for c in cols if c in final_event_log.columns]
    final_event_log = final_event_log[cols]
    
    final_event_log.to_csv(output_file, index=False)
    print(f"\n[Done] Event log successfully saved to {output_file}")
    
    return final_event_log

if __name__ == "__main__":
    event_log_df = build_event_log(
        input_file="merged_traces.csv",
        stats_file="NrDlPdcpStatsE2E.txt",
        output_file="PPM_Event_Log.csv"
    )