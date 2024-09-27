import json
import re

from omnistat.utils import runShellCommand

def expand_number_range(input_str):
    if not isinstance(input_str, str):
        return [input_str]
    # Match the pattern with numbers and ranges inside square brackets
    match = re.search(r'(.+)\[(.+)\]', input_str)
    if match:
        prefix = match.group(1)
        ranges = match.group(2).split(',')
        expanded_list = []

        for item in ranges:
            if '-' in item:
                start, end = map(int, item.split('-'))
                width = len(item.split('-')[0])  # Preserve leading zeros
                expanded_list.extend([f"{prefix}{i:0{width}}" for i in range(start, end + 1)])
            else:
                expanded_list.append(f"{prefix}{item}")

        return expanded_list
    else:
        return [input_str]

def expand_gres_details(gres_details):
    result = []
    expanded_list = []
    for detail in gres_details:
        match = re.search(r'IDX:(\d+)-(\d+)', detail)
        if match:
            start = int(match.group(1))
            end = int(match.group(2))
            expanded_list.extend([f"{i}" for i in range(start, end + 1)])
        result.append(expanded_list)
        expanded_list = []
    return result

def get_job_info():
    # Run scontrol to get job details in JSON format
    result = runShellCommand(['scontrol', 'show', 'jobs', '-d', '--json'], capture_output=True, text=True)
    if result is None:
        return []
    job_info = json.loads(result.stdout)

    # Extract required fields  
    job_data_list = []
    for job in job_info['jobs']:

        job_state = job.get('job_state')[0]

        if job_state == "RUNNING":
            job_node_list = expand_number_range(job.get('job_resources', {}).get('nodes'))
            job_card_list = expand_gres_details(job.get('gres_detail'))
            GPU_list = []

            if len(job_card_list)==len(job_node_list):
                for i in range(len(job_node_list)):
                    node = job_node_list[i]
                    for node_card in job_card_list[i]:
                        GPU_list.append(node + ':' + node_card)
            elif len(job_card_list)<len(job_node_list):
                for i in range(len(job_node_list)):
                    node = job_node_list[i]
                    if i<len(job_card_list):
                        for node_card in job_card_list[i]:
                            GPU_list.append(node + ':' + node_card)
                    else:
                        break
            memory_allocated = job.get('job_resources', {}).get('allocated_nodes', [])[0]['memory_allocated']
            job_data = {
                'job_id': job.get('job_id'),
                'job_state': job.get('job_state')[0],
                'start_time': job.get('start_time', {}).get('number'),
                'end_time': job.get('end_time', {}).get('number'),
                'submit_time': job.get('submit_time', {}).get('number'),
                'nodes': job_node_list,
                'allocated_cpus': job.get('job_resources', {}).get('allocated_cpus'),
                'memory_allocated': memory_allocated,
                'GPUs': GPU_list,
                'user_name': job.get('user_name'),
                'account': job.get('account'),
                'command': job.get('command')
            }
            job_data_list.append(job_data)

    return job_data_list