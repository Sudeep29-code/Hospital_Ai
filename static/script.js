async function loadPatients() {
    const res = await fetch("/api/patients");
    const data = await res.json();

    const tbody = document.querySelector("#queueTable tbody");
    tbody.innerHTML = "";

    document.getElementById("waitingCount").innerText = data.total_waiting;
    document.getElementById("emergencyCount").innerText = data.total_emergency;

    data.patients.forEach(p => {
        const row = document.createElement("tr");

        row.innerHTML = `
            <td>${p.patient_id}</td>
            <td>${p.name}</td>
            <td>${p.oxygen_level}</td>
            <td>${p.bp}</td>
            <td>${p.temperature}</td>
            <td>${p.disease}</td>
            <td class="priority-${p.priority}">${p.priority}</td>
            <td>
                <button class="action complete-btn" onclick="location.href='/complete/${p.id}'">Complete</button>
                <button class="action emergency-btn" onclick="location.href='/emergency/${p.id}'">Emergency</button>
            </td>
        `;
        tbody.appendChild(row);
    });
}

setInterval(loadPatients, 5000);
loadPatients();

function updateCounts() {
    let waiting = 0;
    let emergency = 0;

    const rows = document.querySelectorAll("#queueTable tbody tr");

    rows.forEach(row => {
        const priority = row.children[6].innerText;

        if (priority === "HIGH") {
            emergency++;
        } else {
            waiting++;
        }
    });

    document.getElementById("waitingCount").innerText = waiting;
    document.getElementById("emergencyCount").innerText = emergency;
}

updateCounts();
