import FESTIM
from fenics import *
import sympy as sp


def bc_top_H(t_implantation, t_rest, t_baking):
    cycle_time = ramp_up + plateau + ramp_down + waiting
    t = FESTIM.t
    implantation = (t < t_implantation) * 1
    rest = (t > t_implantation)*(t < t_implantation + t_rest) * 0
    expression = implantation + rest + baking

    return expression


def bc_top_HT(t_implantation, t_rest, t_baking):
    t = FESTIM.t
    implantation = (t < t_implantation) * 1200
    rest = (t > t_implantation)*(t < t_implantation + t_rest) * 343
    baking = (t > t_implantation + t_rest)*(t < t_implantation + t_rest + t_baking)*350
    expression = implantation + rest + baking

    return expression


def bc_coolant_HT(t_implantation, t_rest, t_baking):
    t = FESTIM.t
    implantation = (t < t_implantation) * 373
    rest = (t > t_implantation)*(t < t_implantation + t_rest) * 343
    baking = (t > t_implantation + t_rest)*(t < t_implantation + t_rest + t_baking)*350
    expression = implantation + rest + baking

    return expression


def formulation(parameters, extrinsic_traps, solutions, testfunctions,
                previous_solutions, dt, dx, T, transient):
    ''' Creates formulation for trapping MRE model.
    Parameters:
    - traps : dict, contains the energy, density and domains
    of the traps
    - solutions : list, contains the solution fields
    - testfunctions : list, contains the testfunctions
    - previous_solutions : list, contains the previous solution fields
    Returns:
    - F : variational formulation
    - expressions: list, contains Expression() to be updated
    '''
    k_B = FESTIM.k_B  # Boltzmann constant
    v_0 = 1e13  # frequency factor s-1
    expressions = []
    F = 0

    for material in parameters["materials"]:
        D_0 = material['D_0']
        D_0 = material['D_0']
        E_diff = material['E_diff']
        E_S = material['E_S']
        subdomain = material['id']
        F += (S_0*exp(-E_S/k_B/T)*(solutions[0]-previous_solutions[0])/dt) *\
            testfunctions[0]*dx(subdomain)
        F += dot(D_0 * exp(-E_diff/k_B/T) *
                 grad(S_0 * exp(-E_S/k_B/T)*solutions[0]),
                 grad(testfunctions[0]))*dx(subdomain)

    i = 1  # index in traps
    for trap in parameters["traps"]:

        trap_density = sp.printing.ccode(trap['density'])
        trap_density = Expression(trap_density, degree=2, t=0)
        expressions.append(trap_density)

        energy = trap['energy']
        material = trap['materials']
        F += ((solutions[i] - previous_solutions[i]) / dt) * \
            testfunctions[i]*dx
        if type(material) is not list:
            material = [material]
        for subdomain in material:
            corresponding_material = \
                FESTIM.helpers.find_material_from_id(
                    parameters["materials"], subdomain)
            D_0 = corresponding_material['D_0']
            E_diff = corresponding_material['E_diff']
            alpha = corresponding_material['alpha']
            beta = corresponding_material['beta']
            F += - D_0 * exp(-E_diff/k_B/T)/alpha/alpha/beta * \
                solutions[0] * (trap_density - solutions[i]) * \
                testfunctions[i]*dx(subdomain)
            F += v_0*exp(-energy/k_B/T)*solutions[i] * \
                testfunctions[i]*dx(subdomain)

        F += ((solutions[i] - previous_solutions[i]) / dt) * \
            testfunctions[0]*dx
        i += 1
    return F, expressions


def run(parameters, log_level=40):
    # Export parameters
    FESTIM.export.export_parameters(parameters)

    transient = True

    # Declaration of variables
    dt = 0
    Time = parameters["solving_parameters"]["final_time"]
    initial_stepsize = parameters["solving_parameters"]["initial_stepsize"]
    dt = Constant(initial_stepsize)  # time step size
    set_log_level(log_level)

    # Mesh and refinement
    mesh = FESTIM.meshing.create_mesh(parameters["mesh_parameters"])

    # Define function space for system of concentrations and properties
    V, W = FESTIM.functionspaces_and_functions.create_function_spaces(
        mesh, len(parameters["traps"]))

    # Define and mark subdomains
    volume_markers, surface_markers = \
        FESTIM.meshing.subdomains(mesh, parameters)
    ds = Measure('ds', domain=mesh, subdomain_data=surface_markers)
    dx = Measure('dx', domain=mesh, subdomain_data=volume_markers)

    # Create functions for flux computation
    D_0, E_diff, thermal_cond =\
        FESTIM.post_processing.create_flux_functions(
            mesh, parameters["materials"], volume_markers)

    # Define variational problem for heat transfers
    T = Function(W, name="T")
    vT = TestFunction(W)
    T_n = sp.printing.ccode(
        parameters["temperature"]["initial_condition"])
    T_n = Expression(T_n, degree=2, t=0)
    T_n = interpolate(T_n, W)

    bcs_T, expressions_bcs_T = \
        FESTIM.boundary_conditions.define_dirichlet_bcs_T(
            parameters, W, surface_markers)
    FT, expressions_FT = \
        FESTIM.formulations.define_variational_problem_heat_transfers(
            parameters, [T, vT, T_n], [dx, ds], dt)

    # Define functions
    u, solutions = FESTIM.functionspaces_and_functions.define_functions(V)
    S_W = Function(W)
    S_W = S_0W*exp(-E_SW/FESTIM.k_B/T)
    S_Cu = Function(W)
    S_Cu = S_0Cu*exp(-E_SCu/FESTIM.k_B/T)
    S_CuCrZr = Function(W)
    S_CuCrZr = S_0CuCrZr*exp(-E_SCuCrZr/FESTIM.k_B/T)

    testfunctions_concentrations, testfunctions_traps = \
        FESTIM.functionspaces_and_functions.define_test_functions(
            V, W, 0)

    # Initialising the solutions
    initial_conditions = []
    u_n, previous_solutions_concentrations = \
        FESTIM.initialise_solutions.initialising_solutions(
            V, initial_conditions)
    previous_solutions_traps = \
        FESTIM.initialise_solutions.initialising_extrinsic_traps(
            W, len(extrinsic_traps))

    # Boundary conditions
    print('Defining boundary conditions')
    bcs, expressions = FESTIM.boundary_conditions.apply_boundary_conditions(
        parameters["boundary_conditions"], V, surface_markers, ds,
        T)
    fluxes, expressions_fluxes = FESTIM.boundary_conditions.apply_fluxes(
        parameters["boundary_conditions"], solutions,
        testfunctions_concentrations, ds, T)

    # Define variational problem H transport
    print('Defining variational problem')
    F, expressions_F = FESTIM.formulations.formulation(
        parameters, extrinsic_traps,
        solutions, testfunctions_concentrations,
        previous_solutions_concentrations, dt, dx, T, transient=transient)
    F += fluxes

    du = TrialFunction(u.function_space())
    J = derivative(F, u, du)  # Define the Jacobian

    # Solution files
    files = []
    append = False
    files = FESTIM.export.define_xdmf_files(parameters["exports"])

    derived_quantities_global = \
        [FESTIM.post_processing.header_derived_quantities(parameters)]

    t = 0  # Initialising time to 0s
    timer = Timer()  # start timer

    #  Time-stepping
    print('Time stepping...')
    while t < Time:

        # Update current time
        t += float(dt)
        expressions = FESTIM.helpers.update_expressions(
            expressions, t)
        expressions_form = FESTIM.helpers.update_expressions(
            expressions_form, t)
        expressions_F = FESTIM.helpers.update_expressions(
            expressions_F, t)
        expressions_fluxes = FESTIM.helpers.update_expressions(
            expressions_fluxes, t)
        T_expr.t = t
        T.assign(interpolate(T_expr, W))

        # Display time
        print(str(round(t/Time*100, 2)) + ' %        ' +
              str(round(t, 1)) + ' s' +
              "    Ellapsed time so far: %s s" %
              round(timer.elapsed()[0], 1),
              end="\r")

        # Solve heat transfers
        dT = TrialFunction(T.function_space())
        JT = derivative(FT, T, dT)  # Define the Jacobian
        problem = NonlinearVariationalProblem(FT, T, bcs_T, JT)
        solver = NonlinearVariationalSolver(problem)
        solver.parameters["newton_solver"]["absolute_tolerance"] = \
            1e-3
        solver.parameters["newton_solver"]["relative_tolerance"] = \
            1e-10
        solver.solve()
        T_n.assign(T)

        # Solve main problem
        FESTIM.solving.solve_it(
            F, u, J, bcs, t, dt, parameters["solving_parameters"])

        # Post processing
        FESTIM.post_processing.run_post_processing(
            parameters,
            transient,
            u, T,
            [volume_markers, surface_markers],
            W,
            t,
            dt,
            files,
            append,
            [D_0, E_diff, thermal_cond],
            derived_quantities_global)
        append = True

        # Update previous solutions
        u_n.assign(u)

    # End
    print('\007s')
    return output


parameters = {
    "mesh_parameters": {

        },
    "materials": [
        {
            "D_0":,
            "E_diff":,
            "S_0":,
            "E_S":,
            "id":,
        },
        {
            "D_0":,
            "E_diff":,
            "S_0":,
            "E_S":,
            "id":,
        },
        {
            "D_0":,
            "E_diff":,
            "S_0":,
            "E_S":,
            "id":,
        },
        ],
    "traps": [
        {},
        {},
        {},
        {},
        ],
    "boundary_conditions": [
        {},
        {},
        {},
        ],
    "temperature": {
        },
    "solving_parameters": {
        "final_time": ,
        "initial_stepsize": ,
        "adaptive_stepsize": {
            "stepsize_change_ratio": ,
            "t_stop": ,
            "stepsize_stop_max": ,
            "dt_min": ,
            },
        "newton_solver": {
            "absolute_tolerance": 1e10,
            "relative_tolerance": 1e-9,
            "maximum_iterations": 50,
        }
        },
    "export": {
        "xdmf": {
            "functions": ['solute', '1', '2', '3', 'retention'],
            "labels":  ['solute', 'trap_1', 'trap_2',
                        'trap_3', 'retention'],
            "folder": folder
        },
    }
run(parameters)
