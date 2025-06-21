from django.shortcuts import render
from django.views.decorators.csrf import csrf_exempt
from django.http import JsonResponse
from .models import Compute, Task
from .scheduler import get_run_time, calculate_cost, fetch_rate
import json
import uuid
import os
import requests

@csrf_exempt
def gpu_info(request):
    if request.method == "POST":
        body = json.loads(request.body.decode('utf-8'))

        required = ("uuid", "host", "auth", "flops", "power")
        missing = [f for f in required if f not in body]

        if missing:
            return JsonResponse({"success": False, "message": "Missing fields: " + ", ".join(missing)}, safe=False)

        try:
            uuid = str(body["uuid"])
            host = str(body["host"])
            auth = str(body["auth"])
            flops = int(body["flops"])
            power = int(body["power"])
        except (ValueError, TypeError) as e:
            return JsonResponse({'success': False, 'message': 'Invalid data format'}, safe=False)

        compute = Compute(
            uuid=uuid,
            host=host,
            auth=auth,
            flops=flops,
            power=power
        )
        compute.save()

        return JsonResponse({'success': True}, safe=False)

    else:
        return JsonResponse({'success': False, 'message': 'Invalid request method'}, safe=False)

@csrf_exempt
def addCompute(request):
    if request.method == "POST":
        body = json.loads(request.body.decode('utf-8'))

        required = ("uuid", "rpm", "zip", "dpkwh")
        missing = [f for f in required if f not in body]
        if missing:
            return JsonResponse({"success": False}, safe=False)

        try:
            uuid = str(body["uuid"])
            rpm = float(body["rpm"])
            zip_cd = int(body["zip"])
            dpkwh = float(body["dpkwh"])
        except (ValueError, TypeError) as e:
            return JsonResponse({'success': False}, safe=False)

        compute = Compute.objects.get(uuid=uuid)
        compute.rpm = rpm
        compute.zip = zip_cd
        compute.dpkwh = dpkwh
        compute.save()

        return JsonResponse({'success': True}, safe=False)
    else:
        return JsonResponse({'success': False}, safe=False)

@csrf_exempt
def addTask(request):
    if request.method == "POST":
        body = json.loads(request.body.decode('utf-8'))
        file = request.FILES.get("file")

        if not file or 'latest-time' not in body:
            return JsonResponse({'success': False}, safe=False)

        file_id = str(uuid.uuid4())

        while os.path.exists(f"/tasks/{file_id}.py"):
            file_id = str(uuid.uuid4())

        file_path = f"/tasks/{file_id}.py"

        with open(file_path, "wb") as dest:
            for chunk in file.chunks():
                dest.write(chunk)

        with open(file_path, "r") as f:
            file_cont = f.read()

        min_cost = None
        best_compute = None

        for compute in Compute.objects.all():
            rate = fetch_rate(compute.zip)
            run_time = get_run_time(file_cont, compute.flops, compute.power)
            cost = calculate_cost(run_time, rate, compute.power)

            if not min_cost or cost < min_cost:
                min_cost = cost
                best_compute = compute.uuid

        compute_id = best_compute
        sched_time = 0   # FIGURE OUT WHEN TO RUN / TBD

        new_uuid = str(uuid.uuid4())

        while Task.objects.filter(uuid=new_uuid).exists():
            new_uuid = str(uuid.uuid4())

        task = Task(
            uuid=new_uuid,
            file_path=file_path,
            compute_id=compute_id,
            time=sched_time
        )
        task.save()

        runTask(task)

        return JsonResponse({'success': True}, safe=False)
    else:
        return JsonResponse({'success': False}, safe=False)

def runTask(task):
    compute = Compute.objects.get(uuid=task.compute_id)
    host = getattr(compute, "host")
    auth = getattr(compute, "auth")

    with open(task.file_path, "r") as f:
        file_cont = f.read()

    headers = {"Authorization": "Bearer " + auth}

    resp = requests.post(f"{host}/session", headers=headers, json={"image": "python:3.9-ubuntu20.04", "clientSessionToken": "my-session"})
    session_id = resp.json().sessId

    resp = requests.post(f"{host}/session/{session_id}", headers=headers, json={"code": file_cont, "mode": "query"})
    run_id = resp.json().result.runId
