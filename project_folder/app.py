from flask import Flask, render_template, request, jsonify
import itertools

app = Flask(__name__)

# --- 1. Вспомогательная логика для расчета ---

def get_input_ports(gate_id, circuit_structure):
    """Возвращает список ID входных портов для данного блока."""
    if gate_id not in circuit_structure:
        return []
        
    gate_type = circuit_structure[gate_id]['type']
    
    if gate_type in ['AND', 'OR']:
        return [f"{gate_id}-input1", f"{gate_id}-input2"]
    elif gate_type in ['NOT', 'OUTPUT']:
        return [f"{gate_id}-input1"]
    elif gate_type == 'INPUT':
        return []
    return []

def resolve_input_connection(input_port_id, connections):
    """Находит ID исходящего порта, соединенного с данным входным портом."""
    for conn in connections:
        if conn['to'] == input_port_id:
            return conn['from']
    return None

def evaluate_gate_output(gate_id, port_id, circuit_structure, connections, input_values, cache):
    """
    Рекурсивно вычисляет логическое значение для заданного выходного порта (port_id).
    Предотвращает рекурсию, используя кэш.
    """
    if gate_id not in circuit_structure:
        return 0 
        
    # Проверка на цикличность и использование кэша
    if port_id in cache:
        # Если значение уже в кэше, возвращаем его
        return cache[port_id]

    # Временно устанавливаем значение в 0, чтобы поймать циклы
    cache[port_id] = 0

    gate = circuit_structure[gate_id]
    gate_type = gate['type']
    
    if gate_type == 'INPUT':
        label = gate['label']
        result = input_values.get(label, 0)
    
    else:
        input_port_ids = get_input_ports(gate_id, circuit_structure)
        input_logic_values = []
        
        for input_port_id in input_port_ids:
            source_port_id = resolve_input_connection(input_port_id, connections)
            
            if source_port_id:
                source_gate_id = source_port_id.split('-')[0]
                
                # РЕКУРСИВНЫЙ ВЫЗОВ
                value = evaluate_gate_output(
                    source_gate_id, 
                    source_port_id, 
                    circuit_structure, 
                    connections, 
                    input_values, 
                    cache
                )
                input_logic_values.append(value)
            else:
                input_logic_values.append(0) 

        # Логические операции
        if gate_type == 'NOT':
            val = input_logic_values[0] if input_logic_values else 0
            result = 1 - val
        elif gate_type == 'AND':
            result = 1 if all(input_logic_values) else 0
        elif gate_type == 'OR':
            result = 1 if any(input_logic_values) else 0
        elif gate_type == 'OUTPUT':
            result = input_logic_values[0] if input_logic_values else 0
        else:
            result = 0

    # Обновляем кэш финальным значением
    cache[port_id] = result
    return result

# --- 2. Роуты Flask ---

@app.route('/')
def index():
    """Главная страница, где загружается конструктор схем."""
    return render_template('builder_test.html')

@app.route('/calculate_interactive', methods=['POST'])
def calculate_interactive():
    """Рассчитывает схему для одного заданного набора входных значений."""
    data = request.json
    circuit_structure = data.get('circuit_structure', {})
    connections = data.get('connections', [])
    input_state = data.get('input_state', {})
    
    input_gates = {id: gate for id, gate in circuit_structure.items() if gate['type'] == 'INPUT'}
    output_gates = {id: gate for id, gate in circuit_structure.items() if gate['type'] == 'OUTPUT'}

    if not circuit_structure:
        return jsonify({'input_values': {}, 'output_values': {}})
    
    gate_output_cache = {} 
    output_results = {}
    
    try:
        for output_id, gate in output_gates.items():
            output_port_id = f"{output_id}-output1"
            
            result = evaluate_gate_output(
                output_id, 
                output_port_id, 
                circuit_structure, 
                connections, 
                input_state, 
                gate_output_cache
            )
            output_results[gate['label']] = result
            
    except RecursionError:
        return jsonify({'error': 'Максимальная глубина рекурсии (логический цикл в схеме) превышена.'})
    except Exception as e:
        return jsonify({'error': f"Ошибка расчета: {str(e)}. Проверьте соединения и структуру."})
        
    return jsonify({
        'input_values': input_state,
        'output_values': output_results
    })

@app.route('/calculate_truth_table', methods=['POST'])
def calculate_truth_table():
    """Основная функция для расчета полной таблицы истинности."""
    data = request.json
    circuit_structure = data.get('circuit_structure', {})
    connections = data.get('connections', [])
    
    input_gates = {id: gate for id, gate in circuit_structure.items() if gate['type'] == 'INPUT'}
    output_gates = {id: gate for id, gate in circuit_structure.items() if gate['type'] == 'OUTPUT'}

    if not input_gates or not output_gates:
        return jsonify({'error': 'Схема должна содержать минимум один INPUT и один OUTPUT блок.'})

    input_labels = sorted([gate['label'] for gate in input_gates.values()])
    num_inputs = len(input_labels)
    
    input_combinations = list(itertools.product([0, 1], repeat=num_inputs))
    
    output_labels = sorted([gate['label'] for gate in output_gates.values()])
    headers = input_labels + output_labels
    truth_table = []

    for combination in input_combinations:
        current_input_values = dict(zip(input_labels, combination)) 
        
        gate_output_cache = {} 
        row = list(combination)
        
        try:
            for output_id, gate in output_gates.items():
                output_port_id = f"{output_id}-output1"
                
                result = evaluate_gate_output(
                    output_id, 
                    output_port_id, 
                    circuit_structure, 
                    connections, 
                    current_input_values, 
                    gate_output_cache
                )
                row.append(result)
            
            truth_table.append(row)

        except RecursionError:
            return jsonify({'error': 'Максимальная глубина рекурсии (логический цикл в схеме) превышена.'})
        except Exception as e:
            return jsonify({'error': f"Ошибка расчета: {str(e)}. Проверьте соединения и структуру."})

    return jsonify({
        'headers': headers,
        'table': truth_table
    })

if __name__ == '__main__':
    # Обязательно используйте 'python3 app.py' для запуска
    app.run(debug=True, port=7865)