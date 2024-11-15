app.get('/api/candidate-network', (req, res) => {
    const query = 'SELECT ID, NAME, EMAIL, INSTITUTE, COUNTRY, coauthors FROM Candidate_Rec';

    pool.query(query, (err, results: RowDataPacket[]) => {  // Cast results to Candidate[]
        if (err) {
            return res.status(500).json({ error: err.message });
        }

        // Create a graph representation (adjacency list) for candidates
        const candidateGraph: { [key: string]: Set<string> } = {};  // This will store the nodes and their connections
        const candidateByName: { [key: string]: RowDataPacket } = {}; // Map for fast lookup of candidates by name

        const nodes: { id: string }[] = [];  // Array of nodes for the graph
        const links: { source: string, target: string }[] = [];  // Array of links (edges) for the graph

        // Create a set of all valid candidate names
        const validCandidateNames = new Set(results.map(candidate => candidate.NAME.toLowerCase()));

        // Build the graph
        results.forEach(candidate => {
            const candidateName = candidate.NAME.toLowerCase();
            candidateGraph[candidateName] = candidateGraph[candidateName] || new Set(); // Each candidate is a node
            candidateByName[candidateName] = candidate; // Store candidate by name for easy lookup

            // Add the candidate as a node to the graph
            nodes.push({ id: candidateName });

            // Parse coauthors and filter only those who are valid candidates
            let coauthors: string[] = [];
            if (candidate.coauthors === null || candidate.coauthors === undefined) {
                coauthors = [];
            } else if (Array.isArray(candidate.coauthors)) {
                coauthors = candidate.coauthors;
            } else if (typeof candidate.coauthors === 'string') {
                try {
                    coauthors = JSON.parse(candidate.coauthors);
                } catch (error) {
                    console.error(`Error parsing coauthors for candidate ID: ${candidate.ID}`, error);
                    coauthors = [];
                }
            }

            // Add edges between the candidate and their coauthors (only if the coauthor is a valid candidate and not the candidate themselves)
            coauthors.forEach(coauthor => {
                const coauthorName = coauthor.toLowerCase();
                if (validCandidateNames.has(coauthorName) && coauthorName !== candidateName) {  // Exclude self-connections
                    candidateGraph[candidateName].add(coauthorName);

                    // Add edge to the graph links array
                    links.push({ source: candidateName, target: coauthorName });

                    if (!candidateGraph[coauthorName]) {
                        candidateGraph[coauthorName] = new Set(); // Initialize coauthor as a node if not already added
                    }
                    candidateGraph[coauthorName].add(candidateName); // Add the reverse connection (undirected edge)
                }
            });
        });

        // Build the total network (already done with nodes and links)
        const totalNetwork = { nodes, links };

        // Find the combination of candidates with the least connections among themselves
        const leastConnectedCandidates = Object.keys(candidateGraph)
            .map(candidateName => ({
                name: candidateName,
                connections: candidateGraph[candidateName].size
            }))
            .sort((a, b) => a.connections - b.connections)  // Sort by the fewest connections
            .slice(0, 70);  // Example: Take the top 30 candidates with the fewest connections

        // Build the least-connected subgraph by adding edges between only the selected candidates
        const leastConnectedSubgraph: { nodes: { id: string }[], links: { source: string, target: string }[] } = {
            nodes: leastConnectedCandidates.map(c => ({ id: c.name })),
            links: []
        };

        leastConnectedCandidates.forEach(({ name }) => {
            candidateGraph[name].forEach(coauthorName => {
                if (leastConnectedCandidates.some(c => c.name === coauthorName)) {
                    leastConnectedSubgraph.links.push({ source: name, target: coauthorName });
                }
            });
        });

        // Return both the full network and the subgraph with the least connections
        res.status(200).json({
            totalNetwork,  // The entire network
            leastConnectedSubgraph  // The subgraph with the least connections among candidates
        });
    });
});
